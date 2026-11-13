# Dual INA228 test firmware 0.4.2-ina228-test.1

Source 1cfa116d807b. Built on Raspberry Pi with PM_INA228=1 against official
MeshCore v1.18.0 at 81dbae592ffad40b4212bc0b37e82b38da08f4bc.

Two INA228s: solar 0x40, battery 0x41, R100 (0.100-ohm) shunts. This is a
different sensor profile from the previous INA219 firmware. See the complete
[wiring, modes, telemetry legend and limitations](../../docs/INA228_TEST.md).

Install the UF2 locally, or use the application-only legacy DFU ZIP with a
compatible uploader. No bootloader update is included or required for the
local application install. OTA application activation retains the existing
strict bootloader/storage/signature gates. No automatic flash/activation.

Battery continuous measurement is enabled by default:

```text
pm battery continuous off
pm battery continuous on
pm sensors
pm channels
pm solar
pm load
pm history solar 5m
pm history battery day
```

Off means five-minute single-shot sampling, not disconnecting the battery.
Solar starts with ten-minute single-shot checks; current magnitude >=2mA
starts continuous monitoring. <=0.5mA for thirty seconds returns it to idle.

On-demand telemetry provides latest observations with sample age and both
sensors' observed V/A/signed-W means for 5m/15m/1h/current UTC day. History
channels include measured coverage. Sleeping intervals are not extrapolated;
sparse sampling cannot give exact whole-window energy/current averages.
Firmware uses thirty-second history buckets. Daily totals use double precision.
Records checkpoint every fifteen minutes, so abrupt power loss can lose newer
RAM samples. Persistence uses separate files; old INA219 history is not migrated.

Actual ARM build: BIN389760 bytes, static RAM42632/235520. Firmware HEX/BIN,
UF2 addresses/family/order/bytes, application DFU CRC/S140 B6 and hashes passed.
Native INA228 tests include signed ADC units/polarity, saturation, forward and
reverse solar wake, debounce, observed histories, gaps, UTC rollover/rollback
and four million samples for day precision. Actual full-size signed package
verified with a disposable signer; signature/data/Merkle corruption and
untrusted keys rejected. No production signing key was used for these tests.

Hardware INA228 accuracy, power savings, polarity and extended operation still
need physical testing. No hardware device was flashed by Codex.
