"""Tests for the immutable firmware manifest model (F3-T1)."""

from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from desktop_app.manifest import (
    ChipFamily,
    FirmwareManifest,
    KNOWN_REFERENCE_ARTIFACTS,
    ManifestValidationError,
    lookup_reference,
    load_manifest,
    manifest_from_dict,
    verify_file_sha256,
)


def _good_doc() -> dict:
    return {
        "schema": "keyboard-dm/firmware-manifest/1",
        "name": "kbdm-test",
        "version": "0.0.0-test",
        "chip_family": "esp32c3",
        "flash_size": "4MB",
        "flash_mode": "dio",
        "flash_freq": "80m",
        "images": [
            {"file_name": "bootloader.bin", "offset": 0,
             "sha256": "a" * 64, "size_bytes": 1024},
            {"file_name": "app.bin", "offset": 0x10000,
             "sha256": "b" * 64, "size_bytes": 4096},
        ],
    }


def test_valid_manifest_builds() -> None:
    manifest = manifest_from_dict(_good_doc())
    assert isinstance(manifest, FirmwareManifest)
    assert manifest.chip_family == "esp32c3"
    assert len(manifest.images) == 2
    assert manifest.image("app.bin").offset == 0x10000


def test_manifest_is_immutable() -> None:
    manifest = manifest_from_dict(_good_doc())
    with pytest.raises(AttributeError):
        manifest.version = "nope"  # type: ignore[misc]


def test_unknown_fields_rejected() -> None:
    doc = _good_doc()
    doc["bogus"] = 1
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_wrong_schema_rejected() -> None:
    doc = _good_doc()
    doc["schema"] = "wrong/1"
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_unknown_chip_family_rejected() -> None:
    doc = _good_doc()
    doc["chip_family"] = "esp32s3"
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)
    assert ChipFamily.ESP32_C3 == "esp32c3"


def test_bad_offset_alignment_rejected() -> None:
    doc = _good_doc()
    doc["images"][1]["offset"] = 0x12345
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_negative_offset_rejected() -> None:
    doc = _good_doc()
    doc["images"][0]["offset"] = -1
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_duplicate_offsets_rejected() -> None:
    doc = _good_doc()
    doc["images"][1]["offset"] = 0
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_image_exceeding_flash_size_rejected() -> None:
    doc = _good_doc()
    doc["images"][1]["size_bytes"] = 4 * 1024 * 1024
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_bad_sha256_rejected() -> None:
    doc = _good_doc()
    doc["images"][0]["sha256"] = "xyz"
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)
    doc["images"][0]["sha256"] = "g" * 64
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_empty_images_rejected() -> None:
    doc = _good_doc()
    doc["images"] = []
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_bad_flash_size_rejected() -> None:
    doc = _good_doc()
    doc["flash_size"] = "2MB"
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_missing_required_field_rejected() -> None:
    doc = _good_doc()
    del doc["version"]
    with pytest.raises(ManifestValidationError):
        manifest_from_dict(doc)


def test_load_manifest_roundtrip(tmp_path) -> None:
    path = tmp_path / "m.json"
    path.write_text(json.dumps(_good_doc()), encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.name == "kbdm-test"
    assert [img.file_name for img in manifest.images] == ["bootloader.bin", "app.bin"]


def test_reference_artifacts_load_and_match_f30() -> None:
    by_name = {m.name: m for m in KNOWN_REFERENCE_ARTIFACTS}
    c3 = by_name["kbdm-esp32c3"]
    assert c3.chip_family == ChipFamily.ESP32_C3
    assert c3.version == "f3.0.0"
    assert c3.flash_size == "4MB"
    assert c3.flash_mode == "dio"
    assert c3.flash_freq == "80m"
    assert c3.image("bootloader.bin").offset == 0x0
    assert c3.image("bootloader.bin").size_bytes == 20368
    assert c3.image("bootloader.bin").sha256 == (
        "05c45f65064c5739ed3e53c544469a745b9c9290dcdbc97ae3f888b87b728fd6"
    )
    assert c3.image("partition-table.bin").offset == 0x8000
    assert c3.image("partition-table.bin").size_bytes == 3072
    assert c3.image("partition-table.bin").sha256 == (
        "a11982a2601a607baadac94c0f21fdb7fdbf910249ed5ba58af40be62c2ee98a"
    )
    assert c3.image("kbdm_esp32c3.bin").offset == 0x10000
    assert c3.image("kbdm_esp32c3.bin").size_bytes == 851760
    assert c3.image("kbdm_esp32c3.bin").sha256 == (
        "8074587a345214aaca9399c8798f0b83000c54428cd7eb18601093d324c74fc7"
    )
    assert lookup_reference("kbdm-esp32c3") is c3
    assert lookup_reference("nope") is None
    esp32 = by_name["kbdm-esp32"]
    assert esp32.chip_family == ChipFamily.ESP32
    assert esp32.version == "f3.0.0"
    assert esp32.flash_size == "4MB"
    assert esp32.flash_mode == "dio"
    assert esp32.flash_freq == "40m"
    assert esp32.image("bootloader.bin").offset == 0x1000
    assert esp32.image("bootloader.bin").size_bytes == 26784
    assert esp32.image("bootloader.bin").sha256 == (
        "2e48bc2952504312963c0bd193093cdffd6197f7d0182413be3e297226aa02b1"
    )
    assert esp32.image("partition-table.bin").offset == 0x8000
    assert esp32.image("partition-table.bin").size_bytes == 3072
    assert esp32.image("partition-table.bin").sha256 == (
        "a11982a2601a607baadac94c0f21fdb7fdbf910249ed5ba58af40be62c2ee98a"
    )
    assert esp32.image("kbdm_esp32.bin").offset == 0x10000
    assert esp32.image("kbdm_esp32.bin").size_bytes == 786464
    assert esp32.image("kbdm_esp32.bin").sha256 == (
        "642562e849b515df0442c77299ace34161350fbbac90e93886e96592c44c38fa"
    )


def test_verify_file_sha256(tmp_path, tmp_digest: str = "") -> None:
    path = tmp_path / "f.bin"
    payload = b"hello world" * 1000
    path.write_bytes(payload)
    import hashlib

    good = hashlib.sha256(payload).hexdigest()
    assert verify_file_sha256(path, good) is True
    assert verify_file_sha256(path, "0" * 64) is False
    assert verify_file_sha256(path, good.upper()) is True
