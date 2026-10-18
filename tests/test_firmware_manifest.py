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


def test_reference_artifacts_load_and_match_f21() -> None:
    by_name = {m.name: m for m in KNOWN_REFERENCE_ARTIFACTS}
    c3 = by_name["kbdm-esp32c3"]
    assert c3.chip_family == ChipFamily.ESP32_C3
    assert c3.flash_size == "4MB"
    assert c3.image("kbdm_esp32c3.bin").sha256 == (
        "521b73ce60e2ce6d4da0b88a98a35d0877cb2d2d46c18f5a544dccb603d44f4f"
    )
    assert lookup_reference("kbdm-esp32c3") is c3
    assert lookup_reference("nope") is None
    esp32 = by_name["kbdm-esp32"]
    assert esp32.chip_family == ChipFamily.ESP32
    assert esp32.image("kbdm_esp32.bin").sha256 == (
        "5a76b522e9566a8b07019ba0e4cc3f7ffe7980f0c28c92e9b914dae581766a4d"
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
