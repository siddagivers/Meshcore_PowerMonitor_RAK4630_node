# Dual INA228 + MCP9808 test firmware

Build: `PM_INA228=1 PM_BUILD_SUFFIX=ina228-test.6 bash scripts/build_on_pi.sh official-lora-ota`
in the normal Pi build virtualenv. MeshCore is pinned to
81dbae592ffad40b4212bc0b37e82b38da08f4bc (v1.18.0).
The legacy INA219 profile remains the default without PM_INA228.

## Hardware

Battery INA228: 0x40. Solar INA228: 0x41. Both R100 = 0.100 ohm.
MCP9808: 0x18. Use common ground, SDA/SCL and 3.3-V-compatible pull-ups.
INA228 IDs are checked before configuration; other INA models cannot substitute.
MCP manufacturer/device IDs are checked too. `pm sensors` lists the addresses
and detection state; `pm temp` gives MCP temperature, IDs, raw data and age.
Stock RAK environmental drivers remain enabled, including AHT, SHTC3/SHT4X,
BME280/BMP280, LPS22HB, BME680 and BMP085. Only detected sensors initialize.
BME680 uses raw forced readings in test.5, not cached BSEC IAQ outputs. Add
stock environmental modules before reboot so the startup scan can find them.

RAK15001 in slot C remains the MeshCore OTA staging store: JEDEC C84015, 2 MiB,
CS P0.26. Signed image verification, local pairing/trust and bootloader gates
remain enabled. This application does not replace the bootloader. Verify the
actual device with `pm ota boot` and `pm ota status`; a build alone cannot
establish that the installed bootloader or signer is correctly provisioned.

## Fresh telemetry and radio isolation

The first accepted telemetry request creates a 16-KiB sensor task that waits
between requests and is reused. Each request releases its encoder buffer before
the task hands the result to the radio loop. The task obtains
new INA readings, including a one-shot when the normal mode is sparse, refreshes
the MCP reading and queries the selected environmental drivers. It does not
reuse a previously prepared telemetry response. Sensor conversion latency still
applies: continuously converting temperature devices expose their newest
completed physical conversion. MCP wake waits 300ms; until ready it is omitted.
Failed INA/MCP reads invalidate their current reading rather than reporting zero
or reusing an older reading as fresh. `pm ina off` prevents INA measurements,
including telemetry-triggered ones; MCP and other environmental sensors continue.

The main task owns MeshCore, packets, routing, ACL, crypto and filesystem work.
While the sensor task owns I2C, normal sensor polling and display updates pause.
An external RTC uses an advancing software mirror; hardware clock writes defer.
The radio loop and USB continue. Sensor diagnostics report a task exceeding five
seconds as `sensor stalled; bus isolated`. A truly stuck task is not forcibly
deleted or allowed to collide with another I2C task: future sensor requests
wait, but ordinary MeshCore commands (including reboot) remain available.
`pm diag` and `pm version` remain available while sensor commands report busy.
This protects against sensor-task stalls, not every possible hardware/RTOS fault.

Project-local Wire bounds all eight master event waits (50ms plus a frozen-clock
spin limit). AHT and SHT retry loops are bounded, BME280 calibration waits are
bounded, and test.5 fixes the LPS22HB infinite ONE_SHOT wait/NACK loop. INA-ready
polls run no faster than every 20ms; continuous and triggered conversions have
a 200ms no-ready deadline and failed sensors are re-probed after ten seconds.

## Pages in the official MeshCore app

Run a command in Repeater Admin, then refresh Telemetry:

| Command | Response |
|---|---|
| `pm telemetry live` | Fresh current solar/battery, MCP and environmental readings; default after reboot |
| `pm telemetry power` | Fresh solar/battery V/A/W plus 5m, 15m, 1h and completed previous UTC-day means |
| `pm telemetry environment` | Fresh MCP and supported environmental readings, without INA history |
| `pm telemetry status` | Show selection |

Base battery voltage appears on every page. Selection is global until changed;
it resets to live on reboot. Each response is one page, capped at 163 Cayenne
bytes to leave room for encryption and the request tag. The official app does
not combine arbitrary additional packets into a single telemetry view. With
many extra sensors, add a separate page before exceeding this budget; the
encoder cannot promise unlimited fields. Flooded requests retain the separate
route/data fallback when a combined response is too large. A page change while
a refresh runs applies to the next request; the in-flight request keeps its page.

| Channel | Value |
|---|---|
| 100 / 101 | Fresh solar / battery |
| 102 | MCP9808 temperature (live/environment) |
| 110 / 120 | Solar / battery last 5 minutes |
| 111 / 121 | Solar / battery last 15 minutes |
| 112 / 122 | Solar / battery last hour |
| 113 / 123 | Solar / battery completed previous UTC day |

Voltage is V, Current is signed A, Analog Input is signed W. Battery current is
positive while charging and negative while discharging, subject to wiring
orientation. Percentage is observed coverage; Generic Sensor on 100/101 is age
in seconds. No fake digital-input validity fields are added. App resolution is
1mA for Current and 0.01W for signed Analog Input; CLI has more decimal places.

## Histories and power-saving modes

Battery defaults to continuous; `pm battery continuous off` selects five-minute
one-shots and `... on` restores continuous. Solar checks every ten minutes while
idle, switches continuous at |I| >=2mA, and returns idle after |I| <=0.5mA for
30 seconds. A telemetry request takes an additional fresh observation without
permanently changing the selected mode. `pm ina off/on` is a separate saved
master switch. Supply power is not physically disconnected.

5m/15m/1h means are weighted observations in 30-second buckets. The oldest
partially overlapping bucket is excluded. Single-shot gaps are not extrapolated;
coverage tells how much time was measured. Sparse observations are not an
accurate integral of unmeasured load or solar generation. R100 supports about
plus/minus 1.638A at the selected shunt range; saturation is rejected.

UTC days run 00:00:00 through 23:59:59. Test.5 retains the completed previous
day after midnight, even when no new sensor sample arrives at rollover. It
retains one completed day, not a multi-day archive. Missing days have no invented
values. `pm history solar day` gives today's partial day; `... prevday` gives
the completed previous day. Replace solar with battery for battery history.
Correct device UTC time is required.

Histories checkpoint every 15 minutes and at a main-loop day rollover into two
alternating CRC-checked/read-back files. Power loss can lose recent RAM samples;
filesystem errors are reported. Old INA228 test.4 snapshots are migrated into
the new layout without overwriting identity, radio preferences, credentials,
OTA pairing/trust or old INA219 files. Old snapshots contain no earlier day
that can be reconstructed retroactively.

## Validation and installation

Native tests exercise absent/reconnected sensors, stalled INA-ready flags,
MCP wake/cadence/temperature decoding, asynchronous worker ownership and a
non-progressing worker, history rollover/rollback, old snapshot migration,
previous-day persistence, page limits and OTA transport/crypto. The real ARM
build validates application-only DFU CRC and S140 6.1.1 compatibility. UF2/HEX/BIN
addresses and hashes are checked independently.

Physical multi-day soak testing, actual fault injection, polarity and power
consumption still require hardware testing. No hardware is flashed by the build.
Use the application UF2 on the bootloader drive, or the application DFU ZIP.
Keep the existing bootloader unless its actual compatibility check fails.
