"""Immutable firmware manifest model for the F3 desktop installer.

Defines the manifest document describing which firmware artifacts belong to
a target chip family, at which flash offsets, with which flash characteristics
and SHA-256 digests.

Design rules:
  * Manifests are immutable once loaded (frozen dataclasses, tuples).
  * Validation is strict; failures raise :class:`ManifestValidationError`.
  * Reference artifacts are compile-verified only, never labelled
    hardware-tested.
  * No I/O here: hash checking of actual files lives in the installer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

__all__ = [
    "ChipFamily",
    "FirmwareImage",
    "FirmwareManifest",
    "ManifestValidationError",
    "load_manifest",
    "manifest_from_dict",
    "FLASH_SIZES_BYTES",
    "KNOWN_REFERENCE_ARTIFACTS",
]


class ManifestValidationError(ValueError):
    """Raised when a manifest document fails validation."""


class ChipFamily:
    """Supported chip family identifiers (stable strings in JSON)."""

    ESP32 = "esp32"
    ESP32_C3 = "esp32c3"
    ALL = frozenset({ESP32, ESP32_C3})

    @classmethod
    def check(cls, value: str) -> str:
        if value not in cls.ALL:
            raise ManifestValidationError(f"unknown chip family: {value!r}")
        return value


FLASH_SIZES_BYTES = {"4MB": 4 * 1024 * 1024, "8MB": 8 * 1024 * 1024, "16MB": 16 * 1024 * 1024}
FLASH_MODES = frozenset({"dio", "qio", "dio40m", "qio80m", "qio120m"})
FLASH_FREQS = frozenset({"40m", "80m", "120m"})
_SHA_LEN = 64


def _req_str(doc: Mapping[str, Any], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"field {key!r} must be a non-empty string")
    return value


def _req_int(doc: Mapping[str, Any], key: str, lo: int = 0, hi: int | None = None) -> int:
    value = doc.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestValidationError(f"field {key!r} must be an integer")
    if value < lo or (hi is not None and value > hi):
        raise ManifestValidationError(f"field {key!r} out of range")
    return value


def _req_sha(doc: Mapping[str, Any], key: str) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or len(value) != _SHA_LEN:
        raise ManifestValidationError(f"field {key!r} must be a 64-char hex SHA-256")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ManifestValidationError(f"field {key!r} is not hex") from exc
    return value.lower()


def _req_in(doc: Mapping[str, Any], key: str, allowed: Mapping[str, Any]) -> str:
    value = doc.get(key)
    if not isinstance(value, str) or value not in allowed:
        raise ManifestValidationError(f"field {key!r} must be one of: {sorted(allowed)}")
    return value


@dataclass(frozen=True)
class FirmwareImage:
    """One flashable image: file name, flash offset, SHA-256, size."""

    file_name: str
    offset: int
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if self.offset < 0 or self.offset % 0x1000 != 0:
            raise ManifestValidationError(
                f"offset for {self.file_name!r} must be a non-negative 4 KiB-aligned value"
            )
        if self.size_bytes <= 0:
            raise ManifestValidationError(f"image {self.file_name!r} has invalid size")


@dataclass(frozen=True)
class FirmwareManifest:
    """Immutable description of a complete flashable firmware set."""

    schema: str
    name: str
    version: str
    chip_family: str
    flash_size: str
    flash_mode: str
    flash_freq: str
    images: tuple[FirmwareImage, ...]

    def __post_init__(self) -> None:
        if not self.images:
            raise ManifestValidationError("manifest must contain at least one image")
        offsets = [img.offset for img in self.images]
        if len(set(offsets)) != len(offsets):
            raise ManifestValidationError("image offsets must be unique")
        span = FLASH_SIZES_BYTES.get(self.flash_size)
        if span is not None:
            for img in self.images:
                if img.offset + img.size_bytes > span:
                    raise ManifestValidationError(
                        f"image {img.file_name!r} exceeds declared flash size"
                    )

    def image(self, file_name: str) -> FirmwareImage:
        for img in self.images:
            if img.file_name == file_name:
                return img
        raise KeyError(file_name)


def manifest_from_dict(doc: Mapping[str, Any]) -> FirmwareManifest:
    """Validate a manifest document (dict) and build the immutable object."""

    if not isinstance(doc, Mapping):
        raise ManifestValidationError("manifest must be a JSON object")
    known = {"schema", "name", "version", "chip_family", "flash_size",
             "flash_mode", "flash_freq", "images"}
    unknown = set(doc) - known
    if unknown:
        raise ManifestValidationError(f"unknown fields: {sorted(unknown)}")
    schema = _req_str(doc, "schema")
    if schema != "keyboard-dm/firmware-manifest/1":
        raise ManifestValidationError(f"unsupported schema: {schema!r}")
    name = _req_str(doc, "name")
    version = _req_str(doc, "version")
    family = ChipFamily.check(_req_str(doc, "chip_family"))
    size = _req_in(doc, "flash_size", FLASH_SIZES_BYTES)
    mode = _req_in(doc, "flash_mode", FLASH_MODES)
    freq = _req_in(doc, "flash_freq", FLASH_FREQS)

    raw_images = doc.get("images")
    if not isinstance(raw_images, (list, tuple)) or not raw_images:
        raise ManifestValidationError("field 'images' must be a non-empty array")
    images: list[FirmwareImage] = []
    for entry in raw_images:
        if not isinstance(entry, Mapping):
            raise ManifestValidationError("image entries must be objects")
        img_name = _req_str(entry, "file_name")
        offset = _req_int(entry, "offset")
        digest = _req_sha(entry, "sha256")
        size_bytes = _req_int(entry, "size_bytes", lo=1)
        images.append(FirmwareImage(img_name, offset, digest, size_bytes))

    return FirmwareManifest(schema, name, version, family, size, mode, freq, tuple(images))


def load_manifest(path: str | Path) -> FirmwareManifest:
    """Load and validate a manifest from a JSON file."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return manifest_from_dict(data)


def _ref(name: str, version: str, family: str, size: str, mode: str, freq: str,
         images: tuple[Mapping[str, Any], ...]) -> dict[str, Any]:
    return {
        "schema": "keyboard-dm/firmware-manifest/1",
        "name": name,
        "version": version,
        "chip_family": family,
        "flash_size": size,
        "flash_mode": mode,
        "flash_freq": freq,
        "images": [dict(img) for img in images],
    }


#: Reference artifacts from a clean RTX rebuild on 2026-10-22 using ESP-IDF
#: v5.1.6 and firmware source at commit fe17403. Compile-verified only; NOT
#: hardware-tested and NOT bit-exact reproducible against the original F2.1
#: build because of build-configuration drift. Kept in-repo (no device data).
KNOWN_REFERENCE_ARTIFACTS: tuple[FirmwareManifest, ...] = (
    manifest_from_dict(_ref(
        "kbdm-esp32", "f3.0.0", "esp32", "4MB", "dio", "40m",
        (
            {"file_name": "bootloader.bin", "offset": 0x1000, "sha256":
             "043a925b8f35280a9ba6c3e83e81554d1408fd655abef70dcc105d2b6d7b034e",
             "size_bytes": 26784},
            {"file_name": "partition-table.bin", "offset": 0x8000, "sha256":
             "a11982a2601a607baadac94c0f21fdb7fdbf910249ed5ba58af40be62c2ee98a",
             "size_bytes": 3072},
            {"file_name": "kbdm_esp32.bin", "offset": 0x10000, "sha256":
             "36d2844e9d4c6730aff1b3ac4bff1e354ec2b5fdd12812694d3dfbd3a7716ee4",
             "size_bytes": 786480},
        ),
    )),
    manifest_from_dict(_ref(
        "kbdm-esp32c3", "f3.0.0", "esp32c3", "4MB", "dio", "80m",
        (
            {"file_name": "bootloader.bin", "offset": 0x0, "sha256":
             "9d008db00d5052caf3bdb3038e88e39bdecf87a8861425067eb18eb2d5453641",
             "size_bytes": 20368},
            {"file_name": "partition-table.bin", "offset": 0x8000, "sha256":
             "a11982a2601a607baadac94c0f21fdb7fdbf910249ed5ba58af40be62c2ee98a",
             "size_bytes": 3072},
            {"file_name": "kbdm_esp32c3.bin", "offset": 0x10000, "sha256":
             "24d1c4e991979b3581e44cec61e41645febe87221aee66dc8f4b2df3017287e8",
             "size_bytes": 851840},
        ),
    )),
)


def lookup_reference(name: str) -> FirmwareManifest | None:
    """Find a reference artifact manifest by name (e.g. 'kbdm-esp32c3')."""

    for manifest in KNOWN_REFERENCE_ARTIFACTS:
        if manifest.name == name:
            return manifest
    return None


def verify_file_sha256(path: str | Path, expected_sha256: str) -> bool:
    """Return True when the file's SHA-256 equals the expected digest."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected_sha256.lower()


