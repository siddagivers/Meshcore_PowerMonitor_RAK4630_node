# PowerMonitor 0.4.2-ota-test.4

Source: e0ed10d61a77. Same verification fix and bootloader/storage profile as
bootstrap.4. Install bootstrap.4 locally before testing this update over LoRa.
Use this directory's matching ZIP and JSON in the Pi uploader. Prepare/sign
with the existing trusted signer. A different package starts a fresh transfer.

After explicit successful activation, check remotely:

```text
pm version
pm ota test
```

Expected marker: `OTA update done - TEST4 | PM 0.4.2-ota-test.4 | git e0ed10d61a77`.

BIN: 388984 bytes, static RAM: 42272 / 235520 bytes. Actual ARM compilation,
Nordic application DFU CRC16/S140 B6, HEX/BIN/UF2 layout, manifest hashes and
real full-size signed package software verification passed. No hardware
activation is claimed. See ../../docs/VERIFY_FREEZE_FIX.md for limitations.
