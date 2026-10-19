"""Keyboard DM desktop application package."""

# Packaging reconciliation required: PR #4 reports bootloader SHA differences
# from the frozen c575185 per-family hashes.  Reconcile those artifacts in the
# packaging task; Task 2B intentionally does not update desktop_app.manifest.

from .layout_model import Key, Layout, PROVISIONAL_75_LAYOUT

__all__ = ["Key", "Layout", "PROVISIONAL_75_LAYOUT"]
