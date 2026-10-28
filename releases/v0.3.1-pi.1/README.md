# PowerMonitor 0.3.1-pi.1 — sensor-readout fix and phone DFU ZIP

Official MeshCore v1.18.0-based RAK4631 application. Source commit:
`36aba0a74b178668bc310069d19ec717c26b1c25`; official upstream:
`81dbae592ffad40b4212bc0b37e82b38da08f4bc`.

## Update from the phone

Download **`RAK4631_official_no_lora_ota_PM_v0.3.1-pi.1.zip`** and select
the ZIP directly in a DFU uploader compatible with the installed RAK4631
bootloader's **Nordic/Adafruit legacy DFU 0.5** protocol. Do not extract it.
Enter the board's supported DFU/bootloader mode locally before uploading.

The ZIP contains `manifest.json`, `firmware.dat`, and `firmware.bin`. It is
an **application-only** update requiring the existing **S140 v6.1.1,
SoftDevice ID 0x00B6**. It does not install a bootloader/SoftDevice and is
not a LoRa OTA update. A Secure-DFU-only uploader or a different bootloader /
SoftDevice profile is not interchangeable. Phone transfer has not been tested
by Codex and no device has been flashed by this task.

The DFU application BIN was verified byte-for-byte against the tested HEX/BIN.
Init-packet SoftDevice requirement and **CRC16 0x477C** passed. All files have
SHA256 hashes in the adjacent manifest and `.sha256` file.

## What is corrected

- **INA219:** conversion-ready bit 1 was incorrectly treated as an error in
  0.3.0. It is now accepted. Math-overflow bit 0 is reported separately; the
  driver computes power from raw bus/shunt ADC readings independently of the
  chip's calibrated current/power registers.
- **Two stable INA channels:** 100 = solar at `0x40`; 101 = load at `0x41`.
  The duplicate stock INA219 entry (channel 4 in the user's screenshot) is
  removed. Other native environmental sensors remain enabled.
- **MCP9808:** manufacturer `0x0054` and device family `0x04xx` must match.
  An ACK at `0x18` alone no longer produces a temperature. Confirmed devices
  are woken; unverified/invalid readings are omitted. Legitimate negative
  temperatures stay negative. The cause of the user's -35.31 C reading still
  requires the IDs/raw register from the new `pm temp` diagnostic.
- Missing INA modules and unverified MCP devices are retried every 5 seconds.
- Unavailable sensor readings do not masquerade as a fresh 0-kWh measurement.

## Descriptions in the official client

The client controls the numeric `Channel 100` headings. Standard native
telemetry carries channel/type/value, not custom text labels. Run
**`pm channels`** in Repeater Admin for the description legend.

| Channel | Description |
| --- | --- |
| 100 | Solar INA219, instantaneous V/A/W and cumulative energy |
| 101 | Load INA219, instantaneous V/A/W and cumulative energy |
| 102 | Verified MCP9808 outside temperature |
| 110 | Solar rolling last 15 minutes |
| 111 | Solar rolling last hour |
| 112 | Solar today since 00:00 UTC |
| 113 | Solar yesterday, completed UTC day |
| 114 | Latest checkpoint save/restore status: 1 = success |

Digital Input on 100/101/102 is **reading valid**: 1 = valid, 0 = unavailable.
For history channels, Percentage means **measured-time coverage**, not battery
charge. Generic Sensor is energy in **mWh**; Analog Input is power in **W**.
Native Power has 1-W resolution and native Energy uses kWh, so the phone can
show 0 W / 0.0 kWh despite small nonzero measurements.

After updating, run and send these replies for hardware validation:

```text
pm version
pm solar
pm load
pm temp
```

`pm solar` / `pm load` explicitly label V, mA, mW and cumulative mWh.
`pm temp` returns manufacturer/device IDs and the raw temperature register.
`pm i2c` performs an address-ACK scan. No periodic broadcasts are added.

Older discarded measurements cannot be recovered; coverage fills from valid
new samples after installation. Existing version-3 checkpoints are retained.
Refresh/reopen telemetry if the client retains old cached fields.

## Validation

Integrator, history and new sensor-decoder regression tests passed on the Pi.
Tests cover INA ready/overflow bits, signed current, MCP identity, positive /
negative temperatures and alert flags. Official RAK4631 compilation passed,
using **366,528 / 712,704 flash bytes** and **41,808 / 235,520 static RAM bytes**.
Heap and stacks require additional runtime RAM. HEX/BIN/UF2 equivalence,
address bounds, embedded source/version and hashes passed. See `build.log`,
`verification.json` and the manifest. Physical sensor readings and the phone
upload itself remain to be checked after the user installs this update.
