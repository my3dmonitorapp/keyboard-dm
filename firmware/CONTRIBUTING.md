# Contributing to the firmware foundation

Host-only changes may be developed and tested without a connected device:

```sh
make -C firmware/host clean test
```

Do not infer permission for physical-device work from a successful host or
cross build. The default BSPs intentionally contain no matrix GPIO assignments.

## Connecting your real 9-key board

Follow the ordered gates from F0's PR #2 implementation roadmap. A later gate
cannot waive or retroactively satisfy an earlier one:

1. **F1 — identify and back up.** Positively identify the exact 9-key device,
   chip family/revision, flash size/layout, USB path, power arrangement, matrix
   wiring, diode direction, pulls, and GPIO capabilities. Preserve the current
   state with hashed full-flash and separately identified NVS read-backs where
   supported, plus a reviewed restore procedure and honest recovery
   limitations. This gate is read/backup only: no erase, flash, overwrite,
   configuration upload, or GPIO activation.
2. **Explicit owner authorization.** After the owner reviews the F1 identity,
   backup artifacts, restore plan, and residual risks, obtain separate explicit
   authorization for that exact recorded 9-key device immediately before any
   write. F1 completion and ordinary repository work are not authorization.
3. **F4 — first authorized flash.** Only with that authorization, use the
   compatible family artifact and reviewed manifest/offsets, recheck the backup,
   flash once, verify the written image, reconnect, and preserve the complete
   evidence log. F4 is the first permitted write; F2 performs none, and F3 is
   not implemented here.
4. **F5 — verify all 9 presses.** Upload the reviewed matrix configuration
   without reflashing, then press and release every populated position. Match
   all nine row/column/switch-ID events to the F1 wiring record, reject unsafe
   configurations, power-cycle, and confirm generation, configuration, and
   actions persist.
5. **F6 — run the acceptance loop.** Demonstrate exactly: Keyboard DM ->
   firmware install -> matrix configuration -> save to ESP32 -> Bluetooth
   keypress -> change assignment **without reflashing** -> still works. Retain
   pairing/reconnect, persistence, correct-key, and no-stuck/duplicate-key
   evidence.

This sequence applies only to the F1-recorded 9-key board. It never authorizes
work on the existing 12-key keyboard. The 75-key board has its own later gate.
Nothing in this document performs or authorizes flashing.
