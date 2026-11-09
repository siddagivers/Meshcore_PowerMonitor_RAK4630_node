# PowerMonitor 0.4.2-recovery.5

Firmware source b929d3a40b8a; official MeshCore upstream unchanged.
Application-only recovery release for the existing OTAFIX 2.4.12 / S140 B6
bootloader and RAK15001 slot C configuration. No bootloader update needed.

Install the UF2 via the USB bootloader drive, or use the application ZIP via
the existing compatible DFU uploader when available. Do not format InternalFS.
Identity, settings, signer and pairing file formats remain unchanged.

Changes:
- AHT busy/read-error and SHTC3 NACK retries stop within a bounded 500-ms
  polling window (plus an individual bounded Wire transaction). Failed sensor
  queries are omitted instead of publishing uninitialized events.
- Snapshot restore scans all complete old append-only records and selects
  the newest valid sequence. Saves replace the alternating destination file,
  keep the other slot intact, and check readback length/sequence/checksum.
- OTA status uses the fixed profile capacity while a verification task owns
  QSPI, avoiding concurrent controller activation/deactivation.
- USB boot-stage messages surround stock sensor initialization.

After installation run `pm version`, `pm diag`, `pm sensors`, `pm day`, and
`pm ota status`. Expected version: 0.4.2-recovery.5 git b929d3a40b8a.

Validation: actual ARM compile; 389352-byte BIN; HEX/BIN equivalence; UF2
family/address/order/byte equivalence; app-only Nordic DFU CRC16/S140 B6;
native sensor permanent busy/read-error/NACK/recovery tests; existing power,
history, sensor decoder, polarity and OTA transfer tests; software signature
verification/tamper tests. Hardware startup recovery and long-duration
operation have not been verified. No device was flashed by Codex.
