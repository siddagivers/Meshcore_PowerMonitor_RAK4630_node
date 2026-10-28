# MeshCore Power Monitor — RAK4630 / RAK4631

[![Versioned firmware build](https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node/actions/workflows/firmware.yml/badge.svg)](https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node/actions/workflows/firmware.yml)

**Official MeshCore v1.18.0-based experimental RAK4631 repeater firmware** with dual INA219 power monitoring, MCP9808 outside temperature, native RAK environmental sensors, and on-demand MeshCore telemetry. **LoRa OTA updates are not included.**

## Upstream, version and hardware

- Upstream: [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore), pinned to **`81dbae592ffad40b4212bc0b37e82b38da08f4bc`**. Its repeater header identifies itself as **v1.18.0**.
- Local PowerMonitor version: **0.3.1**, separate from upstream. `pm version` returns the local version and source SHA. This is a custom overlay on official source, not an unmodified official release.
- Base target: **`RAK_4631_repeater`**; overlay target: `RAK_4631_repeater_power_monitor`. Nordic platform 11.0.0 and the upstream framework revision are pinned.
- CI versions: `0.3.1-dev.N`; Pi builds can use `0.3.1-pi.1`. Successful CI jobs publish pre-releases with actual compiled images, hashes and manifests.
- Hardware: **nRF52840 RAK4631 / RAK4630 module on a compatible WisBlock base**, not RAK3401 + RAK13302 1 W.
- **0.1.x and 0.2.x artifacts used the Mesh-America fork**. They remain historical files, not official-upstream builds. 0.1.x also broadcasts power reports. Use 0.3.x for this official-upstream, on-demand, no-LoRa-OTA profile.
- **Codex has not flashed this update. Physical validation of version 0.3.1 is pending.** User screenshots of 0.3.0-dev.9 show both INA addresses responding, roughly 62,000 discarded samples per sensor, and 0% coverage, consistent with the ready-bit bug fixed below.

| Hardware | Role | Address / interface | Schedule |
| --- | --- | --- | --- |
| Generic INA219 | Solar input power / harvested energy | I2C `0x40` | 20-ms polling target |
| RAK16000 INA219 | Load power when shunt is in series with the load | I2C `0x41` | 20-ms polling target |
| MCP9808 | Outside temperature | I2C `0x18` | 60 s |
| RAK1906 BME680/BSEC | Enclosure temperature, humidity, pressure, gas | Native upstream addresses | Native sensor schedule |
| Other supported RAK sensors / GPS | Official RAK4631 sensor support | Native upstream interfaces | Native sensor schedule |
| RAK15001 external flash | **Unused** | No external-flash driver or OTA staging added | None |

The custom driver owns both INA219 devices. The duplicate stock INA219 driver is disabled, as is the stock INA260 driver whose default `0x41` address belongs to the load INA219. Compiler guards enforce these exclusions. Other official RAK sensor support remains inherited. Energy integration uses direct shunt voltage and configured physical shunt resistance, independent of the INA219 calibration register.

### Sensor-readout fix in 0.3.1

Version 0.3.0 incorrectly rejected INA219 bus-register bit 1, which is **conversion ready**, not an error. Version 0.3.1 accepts those samples. Math overflow is bit 0 and refers to the chip's calibrated current/power calculations; this driver computes power directly from raw voltage registers and reports the flag separately in `pm solar` / `pm load` diagnostics. See the [TI INA219 datasheet, bus-voltage register](https://www.ti.com/lit/ds/symlink/ina219.pdf).

MCP9808 detection now verifies manufacturer `0x0054` and device family `0x04xx`, wakes the confirmed device, and suppresses unverified temperatures. A responding device at `0x18` alone is insufficient identification. Real negative MCP9808 temperatures remain signed; the driver does not turn them positive. `pm temp` returns IDs and the raw register for diagnosis. See the [Microchip MCP9808 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/25095A.pdf).

Missing INA modules are retried every five seconds. Older discarded measurements cannot be reconstructed; valid coverage fills after installing the corrected build. Both devices must have different physical I2C addresses; the firmware does not change address jumpers automatically.

## Electrical installation

All I2C sensors share SDA/SCL and 3.3 V logic. Keep a common GND. Verify the generic INA219's address jumpers are open for `0x40`. The RAK16000 uses `0x41`.

**The INA219 does not automatically measure the circuit just because it is connected to the I2C bus. Its shunt MUST be placed in series with the positive supply wire being measured.**

**Solar INA219 (0x40):**

    Solar panel positive -> INA219 VIN+ [shunt] VIN- -> RAK19007 solar charger input
    Solar panel negative -----------------------------> RAK19007 GND

**Consumption INA219 (0x41):**

    Repeater supply positive -> INA219 VIN+ [shunt] VIN- -> complete repeater load positive
    Common ground -------------------------------------> load ground

The RAK19007 charge controller can power the board from solar energy and charge the battery simultaneously. **Battery current is NOT the same as the repeater consumption**. If the RAK16000 is instead inserted into the battery lead, it will measure **battery charge/discharge energy**, and the dashboard should be labeled accordingly. Measuring the *entire board's consumption* may require an external power-path change and must not be attempted by cutting an unknown PCB trace.

**Shunts:** default `0.100 ohm` (typical R100 marking), both channels. Check resistor markings. A 100-milliohm shunt at 700 mA dissipates 49 mW; check shunt current rating and solder connections. If yours differs, edit the `PM_SOLAR_SHUNT_OHMS` / `PM_LOAD_SHUNT_OHMS` values in `scripts/inject.py` before building. Reverse polarity gives negative power; set `PM_SOLAR_SIGN` or `PM_LOAD_SIGN` to `-1` only after verifying the wiring.

This profile adds no LoRa OTA, OTAFIX, EndF trailer, or external-flash staging. It uses the official ExtraFS-safe linker script, limiting the application to `0x26000..0xD3FFF` and preserving the filesystem reservations. The standard RAK4631 board profile specifies S140 v6.1.1; the application cannot install a bootloader or SoftDevice. If a board previously used a custom OTAFIX bootloader, verify its existing bootloader/SoftDevice compatibility locally before changing profiles. No migration or flashing is performed here.

## What is measured, and how accurate is it?

The sampler polls both INA219 devices approximately every 20 ms while preserving the normal repeater radio loop. It reads INA219's 10-microvolt shunt register and 4-millivolt bus-voltage register.

* Current [mA] = shunt voltage [V] / shunt resistance [ohm] × 1000.
* Source-side voltage [V] = bus voltage [V] + shunt voltage [V].
* Power [mW] = source-side voltage [V] × current [mA].
* Energy [mWh] = trapezoidal integral of power [mW] over **actual elapsed milliseconds** / 3,600,000.
* Samples more than 200 ms apart are **not filled in with guesses**. The report includes measured coverage percentage.
* Keep sign: negative readings indicate reversed or genuinely bidirectional flow.
* Store rolling solar 15-minute / 1-hour histories, current UTC-day totals, the previous completed UTC day, and all-time counters separately.

**Important precision limits:** 20 ms is a *target polling interval*, not a guarantee. Radio servicing, other sensor drivers, I2C delays and time spent answering telemetry requests can delay the next sample. INA219's own ADC conversions further limit resolution, and brief TX peaks could still be missed or averaged. Totals should be calibrated against a reference power meter and must not be called exact to the last Wh.

Continuous polling keeps the nRF52840 awake, **raising the idle consumption** compared with sleeping MeshCore firmware. This is a measurement/testing build; afterwards you may choose a slower schedule.

## On-demand native telemetry and saved data

**The power monitor sends no periodic text floods, broadcasts or unsolicited telemetry.** Connect/login to the repeater through your MeshCore client and request or refresh its normal sensor telemetry. Power statistics are appended to the existing authenticated telemetry response; the request's environment-permission mask and guest restrictions remain in effect. Ordinary MeshCore adverts, routing and other upstream features retain their existing behavior. Any over-radio request/reply still uses the normal mesh transport and may need route discovery.

Solar statistics include energy harvested and **average power over measured time** for the rolling last 15 minutes, rolling last hour, today since **00:00 UTC**, and yesterday's completed **00:00:00–23:59:59 UTC** day. Average power does not treat unmeasured time as zero; inspect the coverage percentage alongside it. Day statistics and wall-clock rolling histories require valid UTC time.

| Telemetry channel | Meaning | Fields / units |
| --- | --- | --- |
| 100 | Solar INA219 instantaneous readings and cumulative energy | Voltage V, current A, analog-input signed W, native power W, native energy kWh; Digital Input 1 = current sample valid |
| 101 | Load INA219 instantaneous readings and cumulative energy | Same fields as solar |
| 102 | Verified MCP9808 outside temperature | Temperature °C; Digital Input 1 = valid identified sensor reading, 0 = unavailable |
| 110 | Solar rolling last 15 minutes | Generic sensor **mWh**, analog input **average W**, native energy kWh, percentage coverage |
| 111 | Solar rolling last 1 hour | Same fields |
| 112 | Solar today since UTC midnight | Same fields |
| 113 | Solar yesterday, completed UTC day | Same fields; unavailable days carry 0% coverage without invented energy |
| 114 | Snapshot checkpoint status | Digital input: 1 = saved/restored successfully; 0 = not yet saved or last save failed |

The standard CayenneLPP energy field resolves only **1 Wh** and its power field only **1 W**. To retain useful solar-node precision, the same response includes generic energy in **mWh** and signed analog power in **W with 0.01-W wire resolution**. Client support determines field names, rounding, grouping and whether a refresh is automatic; firmware cannot add a custom named screen to an unchanged client. Clients may show generic channel numbers instead of the descriptions above. The remote admin `pm solar ...` commands below provide precise text readings on demand as well.

Run **`pm channels`** for a compact channel-description legend, **`pm solar`** for explicitly labelled solar V/mA/mW/mWh, and **`pm load`** for the load equivalent. A `0 W` native field can hide sub-watt consumption, and an app displaying `0.0 kWh` can hide a small but nonzero energy total. Use the fine fields or these text diagnostics. The percentage on channels 110–113 is **measurement-time coverage**, not battery charge. Channel 114 value 1 means the latest snapshot save/restore succeeded. The old low-numbered stock INA219 channel (channel 4 in the reported screenshot) was a duplicate solar reading and is no longer added; both INA modules now have stable channels 100/101. Reload telemetry after upgrading if the client retains old cached fields.

Unsigned LPP current/power/energy fields are omitted for negative readings rather than wrapping them into huge positive values. Signed analog power and the read-only diagnostics retain negative values. Values outside a type's range are omitted. The bounded telemetry packet prioritizes these power fields before ordinary external sensors; a fully populated sensor set may not fit in one response, and later sensor fields can be omitted by the existing encoder's size checks.

Energy is still integrated from fast samples, then stored in **10-second history buckets**. Rolling queries omit the partially overlapping oldest bucket, so their boundary resolution is up to 10 seconds; that missing time reduces coverage. Coverage for rolling windows includes startup, outages and sampling gaps. UTC-day coverage compares actual measured time with elapsed time since midnight, or 24 hours for yesterday. Solar data before clock synchronization is not assigned to a calendar day.

Cumulative counters, solar history buckets, today/yesterday solar totals, coverage and a sequence number are saved every 15 minutes and at UTC-day rollover to **two alternating checksummed InternalFS snapshots**. The snapshots use roughly 9 KiB together, share the existing 28-KiB InternalFS with normal repeater data, and never use external flash. Insufficient filesystem space or a failed write is reported by checkpoint status; no partition boundary is expanded. Heap-backed snapshot buffers avoid overflowing the normal repeater loop stack. Sudden power loss can discard samples since the last checkpoint. Restored buckets keep their UTC timestamps, so downtime is not counted as measured time. Version-3 snapshots include this history; old version-2 snapshots are not imported, so upgrading from 0.1.0 starts fresh counters.

## USB and authenticated remote commands

Use a local USB serial terminal at 115200 baud with carriage-return endings, or the repeater's authenticated **admin** command console over MeshCore. Reading commands respond only when requested. Reset remains **local USB only**.

| Command | Result |
| --- | --- |
| `pm version` | Version and embedded source SHA |
| `pm sensors` | Sensors at 0x40, 0x41, 0x18, temperature, error counts, coverage |
| `pm channels` | Plain-language channel map and fine-field units |
| `pm solar` | Labelled solar voltage, mA, mW, cumulative mWh, raw-ADC status and math-overflow flag |
| `pm load` | Equivalent load readings, or explicit missing/read-error status |
| `pm temp` | MCP9808 identity status, manufacturer/device IDs, raw temperature register and decoded °C |
| `pm i2c` | Read-only I2C address-ACK scan; an ACK does not identify a sensor model |
| `pm status` | Since-boot/cumulative mWh, voltage and current |
| `pm day` | UTC-day solar/load totals and snapshot recovery count |
| `pm solar 15m` | Rolling 15-minute solar mWh, measured-time average W and coverage |
| `pm solar 1h` | Rolling 1-hour solar statistics |
| `pm solar today` | Solar statistics since 00:00 UTC |
| `pm solar yesterday` | Previous completed UTC-day solar statistics |
| `pm info` | Sampler interval, shunt values and firmware version |
| `pm reset YES` | Local USB only: reset energy totals/history and checkpoint zeroes |

## Compile on Raspberry Pi / Debian

Requirements: Git, Python 3 with venv, PlatformIO CLI, internet access to download the pinned MeshCore version + Nordic toolchain, and free disk space.

```bash
sudo apt update
sudo apt install -y git python3-venv build-essential
git clone https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node.git
cd Meshcore_PowerMonitor_RAK4630_node
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
bash tests/run_tests.sh
bash scripts/build_on_pi.sh official
```

Source is cloned from official [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore) into ignored `upstream-official/` and checked out at **`81dbae592ffad40b4212bc0b37e82b38da08f4bc`**. The strict overlay checks each integration anchor, adds sampling to the repeater loop, and appends power statistics to native telemetry after guest restrictions are applied. Remote text commands retain upstream admin authentication. Reset is accepted only by the local USB hook; a remote zero timestamp does not grant reset access. Long MCU sleeps are disabled for high-rate sampling. **The build script never uploads or flashes firmware.**

Use `bash scripts/build_on_pi.sh official`, or omit the argument. Previous `rak15001`, `w25q16` and `unified` arguments are rejected rather than silently selecting another hardware profile.

Outputs use `RAK4631_official_no_lora_ota_PM_v0.3.1-pi.1` names under `output/`: HEX, BIN, UF2, application DFU **ZIP**, `.sha256` and manifest `.json`. The manifest records the official upstream URL/revision/version, local source commit, UTC build time, image sizes/hashes, application bounds, and `lora_ota: false`.

### Phone DFU uploader

Select the versioned **`.zip` directly**, without extracting it, in a phone uploader supporting the installed RAK4631 bootloader's **Nordic/Adafruit legacy DFU 0.5** protocol. The ZIP contains the real application binary, init packet and Nordic manifest; it is not an archive of UF2/HEX files. It requires the existing **S140 v6.1.1 SoftDevice ID `0x00B6`** and does not install a bootloader or SoftDevice. Enter the board's supported DFU/bootloader mode locally before using the uploader. Do not substitute a Secure-DFU-only uploader or a different board/SoftDevice profile. The build verifies BIN equality and CRC16; phone transfer has not been tested by Codex. This local bootloader DFU path is separate from LoRa OTA and does not enable LoRa OTA.

The raw BIN starts at **0x26000**. UF2 embeds destination addresses and uses family **0xADA52840**. Packaging rejects data at or above **0xD4000**, preserving the official ExtraFS reservation. These are application-only images, not combined bootloader/SoftDevice images or LoRa OTA packages. No custom EndF/OTAFIX trailer is generated. **Do not rename BIN to UF2 or use these images with the old fork's OTA apply commands.**

The separate 1 W RAK3401 + RAK13302 project remains [Lora_OT_Lora_UPDATE_1wRak](https://github.com/siddagivers/Lora_OT_Lora_UPDATE_1wRak).

## GitHub Actions builds, releases and versioning

The workflow [`.github/workflows/firmware.yml`](.github/workflows/firmware.yml) runs the C++ host integration test and builds the official no-LoRa-OTA RAK4631 configuration from scratch on each push to `main`, or via **Actions > Versioned RAK4631 firmware > Run workflow**.

* **Development build:** repository `VERSION` = `0.3.1`; Actions run number = `N`; binary reports `0.3.1-dev.N`.
* **CI artifacts:** every *successful* job provides a downloadable versioned archive under its Actions run.
* **GitHub Releases:** once the compiler and tests pass, the workflow publishes `v0.3.1-dev.N` as a **pre-release** with actual compiled files plus hashes. A failed build **must not** produce a flashable release.
* **Traceability:** `pm version` and the adjacent build-manifest JSON identify the exact source commit.

Version policy: increment `VERSION` for intentional feature/compatibility changes; CI run numbers disambiguate rebuilds of the same source revision. Pre-release means **not hardware-qualified**. Only upgrade to a stable `v1.0.0` after bench tests, 1-hour cumulative measurement comparison, unexpected-reset tests, and a successful recovery drill.

## Hardware verification before installing remotely

### Compiler and test verification

Host tests cover the integrator, signed readings, timer wrap, rolling histories, gaps, restored state, UTC midnight rollover, skipped days, clock rollback and telemetry units. Versioned Pi snapshots in `releases/` include build logs, source manifests and artifact-verification evidence. The official port uses ordinary PlatformIO size checks; old fork-specific runtime-RAM and DFU-handoff checks are **not** part of this build. Compiler success is not a physical sensor, radio, bootloader, power-interruption, or client presentation test.

This build uses GCC ARM 14.2.1 and `-Os`, removing the framework's `-Ofast`. No application region is enlarged and no fork OTA/framework patches are copied over.

The official-source port compiled on a Raspberry Pi 5 running aarch64 Linux, using approximately **366 kB flash / 42 kB static RAM**. Its versioned manifest records exact sizes. Counter reset clears history in place, avoiding a multi-kilobyte temporary on the stock Arduino loop stack; snapshot buffers remain heap-backed.

### Bench and recovery checklist

1. Confirm RAK4631 core identity and standard board/SoftDevice/bootloader compatibility locally. This application does not install them.
2. Verify normal MeshCore radio operation on the bench before using experimental power-monitor images.
3. Use `pm version` and `pm sensors` over USB to confirm all three I2C devices and the desired firmware SHA.
4. Put a known load in series with INA219 `0x41`; measure bus voltage and peak TX current with a separate reference meter.
5. Request telemetry after 15 minutes and 1 hour, and across UTC midnight; compare rolling/day mWh and coverage with a calibrated power meter. Check wake/idle power penalty.
6. Verify the application ends below `0xD4000` and ordinary USB recovery works locally; LoRa OTA is outside this profile.
7. Test watchdog/reset/checkpoint behavior, reboots and power interruptions. Only then plan a remote deployment.

### Troubleshooting

* Linker overflow: do not enlarge the application region. Check the official ExtraFS-safe limit and resolved `-Os` compiler flags.
* Missing `intelhex`: activate the build venv and run `pip install -r requirements-build.txt`; IntelHex converts the official application HEX to BIN.
* Pi SSH reports `Permission denied (publickey,password)`: specify the installed private key with `ssh -i <private-key-path> -o IdentitiesOnly=yes pi@<pi-address>`. A successful TCP connection followed by this error is an authentication problem. A timeout or unreachable route is a network problem; try the Pi's LAN address while on its LAN, or its Tailscale address with an active Tailscale connection. Never commit SSH private keys or passwords.
* `solar40:MISSING`: check the generic INA219's A0/A1 address and I2C pull-ups; verify 3.3 V logic.
* `load41:MISSING`: RAK16000 must actually use `0x41`; verify I2C connection.
* `mcp18:MISSING`: MCP9808 should be `0x18`; check its A0/A1/A2 straps.
* 0 or incorrect energy: check series shunt wiring, direction and resistor value; do not confuse battery current with repeater consumption.
* Build failure: open GitHub Actions logs; do not flash an unverified artifact.
* Missing power telemetry: login with environment-sensor access, explicitly refresh telemetry, and verify UTC time. Use the authenticated admin console with `pm solar 15m` for precise diagnostic output.

**Safety:** Solar charging is an electrical power-management function, not a regulated laboratory supply. Never insert current monitors between Li-ion battery terminals without appropriate insulation, current limits and short-circuit protection.

## References

* [Texas Instruments INA219](https://www.ti.com/product/INA219)
* [RAK16000 module](https://docs.rakwireless.com/product-categories/wisblock/rak16000/)
* [Official MeshCore RAK4631 configuration](https://github.com/meshcore-dev/MeshCore/blob/81dbae592ffad40b4212bc0b37e82b38da08f4bc/variants/rak4631/platformio.ini)
