# Keyboard DM v0.1 finish line

## v0.1 scope

Keyboard DM v0.1 delivers a universal configuration architecture. A user can
define the keyboard matrix, GPIO assignments, and key layout in the GUI, with
the configuration validated for the selected chip family. A blank device must
remain safe to boot before configuration. After firmware flashing, the desktop
application transfers the validated configuration over USB serial and the
firmware stores it in NVS; the same device can then be reconfigured without a
reflash.

ESP32 and ESP32-C3 are the only chip families in v0.1 scope. ESP32-S3 is a
future-adapter-only target. No new chip families will be added in v0.1.

## Exactly four remaining checkpoints

1. **F3-T6 — main-window installer integration.** The existing installer panel
   is reachable from the real Keyboard DM main window; a complete mock install,
   cancellation, and return-to-editor regression are covered by offscreen GUI
   tests; the complete GUI/regression suite is green; and PR #4 is published.
2. **Blank-device provisioning and desktop-to-firmware serial configuration.**
   A configuration accepted by chip-family validation is transferred from the
   desktop application over USB serial, stored in NVS by a blank-device-safe
   firmware, read back or otherwise verified, and can be changed and applied
   again without reflashing firmware.
3. **Real ESP32-C3 flashing, backup, and reconnect.** The real backend safely
   identifies an ESP32-C3, creates and verifies a complete pre-flash backup,
   flashes the approved images, verifies them, and reconnects to the expected
   protocol. Every physical read/write/erase operation remains locked behind
   explicit operator authorization and is validated without weakening that
   gate.
4. **Real nine-key hardware acceptance.** With separate explicit approval and
   verified GPIO wiring, one real device passes: detect -> validated 9-key
   config -> backup -> authorized install -> serial config transfer -> BT pair
   -> physical key actions -> change action without reflash -> reboot
   persistence.

## Verified state at time of writing

- Code range: `a24cb20..33dff1d` (F3-T1 through the recorded F3-T5 checkpoint),
  plus the uncommitted F3-T6 working-tree changes described here.
- `./.venv/bin/python -m pytest tests -q`: **302 passed**.
- `./.venv/bin/python -m pytest tests/test_gui_installer_integration.py -v`:
  **4 passed** (installer reach + return, full mock install with restored
  backup digest, cancellation to CANCELLED, editor-page regression after
  returning from the installer page).
- The end-to-end installer workflow, backup contents and digest, flash
  verification, reconnect, cancellation, and main-window integration are
  verified with injected ports and `MockFlashBackend`; they do not touch serial
  ports or hardware.
- Firmware manifests, compatibility checks, installer state transitions, and
  authorization-denial behavior have automated coverage. `RealFlashBackend`
  identification is only an adapter scaffold, while its backup, flash, and
  erase operations remain both authorization-gated and unimplemented. No real
  ESP32/ESP32-C3 device workflow was run for this checkpoint.

## Blocking issues

- The desktop-to-firmware serial configuration protocol and its NVS persistence
  path are not integrated end to end.
- Blank-device provisioning and safe configuration recovery are not validated
  on physical hardware.
- The real flash backend is not wired for backup, write, verification, or
  reconnect; physical operations still require an explicit authorization flow.
- Bluetooth pairing and keyboard input verification are not integrated into an
  acceptance flow.
- The nine-key physical rig, its GPIO wiring, and the separately approved
  hardware acceptance run remain outstanding.
- PR #4 (`feature/f3-desktop-installer`) carries this commit; it remains a
  draft pending review.

## Not in v0.1

- RGB
- macros
- layers
- commercial manufacturing
- themes
- additional ESP32 families
- OS packaging
- unrelated UI redesign
