# Provisional hardware notes — 9-key board (recovered 2026-10-18)

> **Status: PROVISIONAL.** This is recorded operator information, **not**
> an approved GPIO mapping. The matrix, GPIO pins, and diode scan
> orientation have NOT been electrically verified. Do not use any content
> of this file as a flashable or hardcoded GPIO configuration.

Board confirmed by the operator:

- ESP32-C3 revision 0.4, 4 MB flash
- ESP32-C3 Super Mini board
- Native USB-Serial/JTAG working
- Secure Boot: disabled
- Flash Encryption: disabled
- Original firmware: Arduino / NimBLE / HijelHID
- Full 4 MB original flash backup exists (stored privately; never in Git)
- 9 switches, each with an individual diode
- Physical inspection: diode black-striped (cathode) ends face the
  ESP32-side wiring; opposite (anode) ends connect to the switch side.
  **Scan polarity is therefore suspected but NOT confirmed electrically.**

Suspected but unverified:

- Electrical matrix suspected to be 2 rows x 5 columns (or 5 x 2).
- GPIO assignments: unknown.
- Diode scan orientation (push-pull vs pull-up, row/col direction): unknown.

Action items for first real installation (F4+):

1. Logically identify each GPIO on the C3 (pin 1 = D1, etc.).
2. Continuity-measure every switch corner against the ESP32 side.
3. Determine matrix topology and scan polarity with a multimeter;
   record the verified map only after electrical confirmation.
4. Keep this file as provenance, never as configuration.
