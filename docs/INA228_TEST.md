# Dual INA228 test profile

Build using `PM_INA228=1 PM_BUILD_SUFFIX=ina228-test.1 bash scripts/build_on_pi.sh official-lora-ota`
inside the normal Pi build virtualenv. Official MeshCore remains pinned to
81dbae592ffad40b4212bc0b37e82b38da08f4bc (v1.18.0).
The legacy INA219 profile remains the default when PM_INA228 is absent.

## Hardware

Two genuine INA228 devices, solar 0x40 and battery 0x41, R100 = 0.100 ohm
shunts on both. Share ground/SDA/SCL and use 3.3-V-compatible I2C pull-ups.
Raw manufacturer/device IDs are checked before configuration; INA219, INA226
and INA238 are not interchangeable. Conflicting stock power-sensor probes
are disabled. MCP9808 is not part of this test profile. Stock environmental
sensors still use the earlier bounded AHT/SHT driver fixes.

The normal +/-163.84-mV shunt range supports roughly +/-1.638 A with R100.
Saturated readings are rejected. Bus voltage uses 195.3125 uV/count and signed
shunt voltage uses 312.5 nV/count. Current = shunt voltage / measured shunt
resistance; signed power = bus voltage * signed current. The hardware energy
and charge accumulators are not used. Component tolerance and offsets still
require physical calibration/verification. Battery orientation is the previous
discharge-positive raw convention, inverted for positive charging and negative
discharging. Swap the two sense leads if physical direction is opposite.

Source: https://www.ti.com/lit/ds/symlink/ina228.pdf

## Sampling modes

Battery defaults to continuous ADC conversion, host observations every 20 ms.
`pm battery continuous off` selects one triggered conversion every 5 minutes;
the INA228 returns to ADC shutdown between conversions. `pm battery continuous on`
restores continuous conversion. The choice is stored separately in InternalFS.
The battery power circuit is never switched off by this setting.

Solar starts with a single-shot check. At >=2 mA current magnitude it switches to
continuous conversion (including reverse leakage). At <=0.5 mA magnitude for 30 seconds it switches to a ten-minute
single-shot cadence. This hysteresis avoids chatter around noisy zero readings.
Generation beginning between checks can be missed for up to ten minutes.
Both devices remain supplied; shutdown stops their ADC conversion. The host
and MeshCore receiver remain running, so total board sleep current is not
claimed. A conversion deadline prevents an absent/not-ready device from
blocking the repeater; reconnection is retried every ten seconds.

## Histories and accuracy

Both sensors store weighted mean voltage, signed current and signed power for
5 minutes, 15 minutes, 1 hour, and the current UTC day since 00:00. `day` is
not a rolling 24-hour window. Histories use thirty-second buckets; the oldest
partially overlapping bucket is excluded. Time-weighted continuous observations
have full coverage except gaps/boundaries. Single shots contribute short
observation weights only: the firmware never assumes their current persisted
over the entire five/ten-minute sleep interval. Consequently sparse-mode means
describe sampled time, not an accurate whole-window energy integral.
No means are reported when a window contains no observations.

History is held in RAM immediately and checkpointed every 15 minutes to two
alternating, checksummed `/pm228.a` and `/pm228.b` files with readback checks.
Power failure can lose observations since the last checkpoint. Existing INA219
histories are left intact and are not converted. `pm sensors` reports whether
a history checkpoint has restored/saved successfully; until then it reports
not saved yet/FS error. UTC must be set correctly for histories to be useful.

## On-demand MeshCore telemetry

No unsolicited telemetry advertisements are added. Request telemetry normally
as an authenticated client with environmental telemetry permission.

| Channel | Meaning |
|---|---|
| 100 | Latest solar observation |
| 101 | Latest battery observation |
| 110 / 120 | Solar / battery 5-minute observed means |
| 111 / 121 | Solar / battery 15-minute observed means |
| 112 / 122 | Solar / battery 1-hour observed means |
| 113 / 123 | Solar / battery current UTC-day observed means |

Voltage = V; Current = signed A; Analog Input = signed W. Percentage on history
channels is measured coverage. Generic Sensor on 100/101 is sample age in
seconds. Thus latest readings in sparse mode are explicitly aged observations,
not necessarily fresh current. Official client channel headings cannot be
renamed by the repeater firmware. Native Cayenne current resolution is 1 mA,
and signed analog power resolution is 0.01 W. CLI readings show more precision.
All ten V/I/P groups plus coverage/age use at most 156 telemetry bytes; the
180-byte stock buffer bounds any additional stock sensors.

Commands:

```text
pm version
pm diag
pm sensors
pm channels
pm solar
pm load
pm battery continuous off
pm battery continuous on
pm history solar 5m
pm history solar 15m
pm history solar 1h
pm history solar day
pm history battery 5m
pm history battery 15m
pm history battery 1h
pm history battery day
```

Install the application UF2 locally for this sensor migration. Keep the existing
bootloader; no bootloader is included or automatically changed. OTA activation
remains blocked if the installed bootloader/profile does not match. Existing
identity, radio settings and passwords are not intentionally modified, and no
device is flashed by the build. Keep the recovered identity backup.

Native tests cover signed 20-bit decoding, units, battery polarity, saturation,
solar hysteresis, weighted histories, gaps and UTC rollover/rollback. The build
also checks HEX/BIN/UF2 layout and DFU CRC/S140 compatibility. Actual INA228
measurements, sleep current, polarity and long-duration behavior require device
testing; software tests do not establish those hardware results.
