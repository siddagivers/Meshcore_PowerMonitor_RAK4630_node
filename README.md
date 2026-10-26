# MeshCore Power Monitor — RAK4630 / RAK4631

[![Versioned firmware build](https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node/actions/workflows/firmware.yml/badge.svg)](https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node/actions/workflows/firmware.yml)

**Experimental MeshCore repeater firmware for solar-powered RAK4630/RAK4631**, integrating two INA219 power monitors at 20-ms target intervals, an MCP9808 temperature sensor, and the ordinary supported RAK WisBlock environmental sensors. RAK15001 SPI NOR remains owned by the OTA bootloader.

## Version, status and supported hardware

* Firmware version: **0.1.0 development** (see [VERSION](VERSION)).
* Successful CI build versions: `0.1.0-dev.N`, where `N` is the GitHub Actions run number.
* Successful CI jobs publish a GitHub **pre-release** with a `v0.1.0-dev.N` tag, firmware files, SHA-256 hashes, and build metadata.
* The firmware contains the same version and source commit; read over USB with `pm version`.
* **NOT yet bench-validated on a physical RAK4631.** Do not OTA-flash your only remote repeater with a development image.
* This is an **nRF52840 / RAK4631 repeater build**, not the RAK3401 + RAK13302 1 W hardware.

| Hardware | Role | I2C address / bus | Poll target |
| --- | --- | --- | --- |
| Generic INA219 | Solar panel input power and accumulated mWh | `0x40` | **20 ms** |
| RAK16000 INA219 | Actual load power *only when the shunt is wired in series with the load* | `0x41` | **20 ms** |
| MCP9808 | Outside temperature | `0x18` | **60 s** |
| RAK1906 BME680/BSEC | Inside enclosure: temperature, humidity, pressure, gas | Typically `0x76` or `0x77` | Native MeshCore schedule |
| Other standard supported RAK sensors | Stock MeshCore sensors + radio/CLI | Their ordinary addresses | Native MeshCore schedule |
| RAK15001 (2 MiB NOR) | Full/delta mOTA firmware staging | WisBlock SPI, sensor slot **C** | OTA only |

The stock MeshCore INA219 sensor driver at `0x40` is left operational. The stock INA260 driver at `0x41` is disabled to prevent it confusing the second INA219 with an INA260. INA219 energy measurements do not require programming the INA219 calibration register: current is calculated from the directly measured shunt voltage and a configured physical shunt resistance.

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

RAK15001 must occupy **sensor slot C** with the exact matched **RAK4631_RAK15001_C** firmware and compatible **OTAFIX** bootloader. A matching `.uf2` is an *application image* and cannot migrate a stock bootloader into the custom OTAFIX profile. Use the official board-specific combined bootloader + SoftDevice procedure for the one-time migration. Never install the RAK15001 profile on a RAK3401 + RAK13302 1 W board.

## What is measured, and how accurate is it?

The sampler polls both INA219 devices approximately every 20 ms while preserving the normal repeater radio loop. It reads INA219's 10-microvolt shunt register and 4-millivolt bus-voltage register.

* Current [mA] = shunt voltage [V] / shunt resistance [ohm] × 1000.
* Source-side voltage [V] = bus voltage [V] + shunt voltage [V].
* Power [mW] = source-side voltage [V] × current [mA].
* Energy [mWh] = trapezoidal integral of power [mW] over **actual elapsed milliseconds** / 3,600,000.
* Samples more than 200 ms apart are **not filled in with guesses**. The report includes measured coverage percentage.
* Keep sign: negative readings indicate reversed or genuinely bidirectional flow.
* Track 15-minute windows, UTC-day counters and all-time counters separately.

**Important precision limits:** 20 ms is a *target polling interval*, not a guarantee. Radio servicing, other sensor drivers, I2C delays and time spent transmitting reports can delay the next sample. INA219's own ADC conversions further limit resolution, and brief TX peaks could still be missed or averaged. Totals should be calibrated against a reference power meter and must not be called exact to the last Wh.

Continuous polling keeps the nRF52840 awake, **raising the idle consumption** compared with sleeping MeshCore firmware. This is a measurement/testing build; afterwards you may choose a slower schedule.

## Reporting and saved data

One **MeshCore Repeaters-channel flood text** is queued every **15 minutes**. Example:

```text
PM15 S=38.500mWh L=16.230mWh D=97.51/65.38 T=12.2C V=5.35/4.08 C=99/98%
```

* `S` solar energy during the report interval (mWh).
* `L` measured load energy during the report interval (mWh), not automatically battery current.
* `D` today's solar/load mWh, once the clock has valid UTC; before then this is a running counter.
* `T` MCP9808 external temperature (°C).
* `V` solar/load supply voltages (V).
* `C` measured-time coverage of solar/load windows (%).

This is best-effort MeshCore flooding; a queued packet is **not** proof your Raspberry Pi received it. If queueing fails, firmware retries after 30 seconds without discarding the interval accumulation. Native MeshCore environmental telemetry remains available separately.

Cumulative energy, day totals and a sequence number are saved every 15 minutes to **two alternating checksummed InternalFS snapshots**, independent of the external RAK15001. A sudden power cut can lose energy recorded after the last checkpoint. A device clock reset cannot recover accurate calendar-day boundaries until time synchronizes.

## USB serial commands

Connect a **local** serial terminal at 115200 baud and use carriage-return line endings. These commands are implemented only on the local USB console; ordinary MeshCore remote-admin text commands are not modified.

| Command | Result |
| --- | --- |
| `pm version` | Version and embedded source SHA |
| `pm sensors` | Sensors at 0x40, 0x41, 0x18, temperature, error counts, coverage |
| `pm status` | Window/cumulative mWh, voltage and current |
| `pm day` | UTC-day solar/load totals and snapshot recovery count |
| `pm report` | Preview next mesh report without transmitting |
| `pm report off` | Disable 15-minute flood until reboot or re-enable |
| `pm report on` | Resume periodic floods |
| `pm info` | Sampler interval, shunt values and firmware version |
| `pm reset YES` | Reset energy totals and checkpoint zeroes |

## Compile on Raspberry Pi / Debian

Requirements: Git, Python 3 with venv, PlatformIO CLI, internet access to download the pinned MeshCore version + Nordic toolchain, and free disk space.

```bash
sudo apt update
sudo apt install -y git python3-venv build-essential
git clone https://github.com/siddagivers/Meshcore_PowerMonitor_RAK4630_node.git
cd Meshcore_PowerMonitor_RAK4630_node
python3 -m venv .venv
source .venv/bin/activate
pip install -U platformio
bash tests/run_tests.sh
bash scripts/build_on_pi.sh rak15001
```

Source is pinned to upstream [Mesh-America MeshCore](https://github.com/Mesh-America/mesh-america-quake-repeater) revision **`c908bb09e68ca81e1d19198776e0f2e5b7e48653`**. The injection script checks exact integration anchors, patches the repeater's main event loop and adds a separate PlatformIO environment called `RAK_4631_repeater_power_monitor`. **It never flashes connected hardware.**

Outputs are written to `output/` with names such as `RAK4631_rak15001_PM_v0.1.0-local.20261026210000.hex`; when supported by the toolchain, matching `.uf2` and `.bin` files are also collected. Each build also produces `.sha256` and JSON metadata with the exact build's source commit, upstream revision, UTC date and output-file hashes. **Do not rename a BIN to UF2.**

Alternative build targets (different **hardware and bootloader**):
* `bash scripts/build_on_pi.sh w25q16` — RAK4631 with separately wired Winbond W25Q16 flash, matching dedicated application and bootloader.
* `bash scripts/build_on_pi.sh unified` — adaptive RAK4631 storage target, appropriate matching bootloader mandatory.

The 1 W RAK3401 + RAK13302 project is separate: [Lora_OT_Lora_UPDATE_1wRak](https://github.com/siddagivers/Lora_OT_Lora_UPDATE_1wRak).

## GitHub Actions builds, releases and versioning

The workflow [`.github/workflows/firmware.yml`](.github/workflows/firmware.yml) runs the C++ host integration test and builds the RAK15001 configuration from scratch on each push to `main`, or via **Actions > Versioned RAK4631 firmware > Run workflow**.

* **Development build:** repository `VERSION` = `0.1.0`; Actions run number = `N`; binary reports `0.1.0-dev.N`.
* **CI artifacts:** every *successful* job provides a downloadable versioned archive under its Actions run.
* **GitHub Releases:** once the compiler and tests pass, the workflow publishes `v0.1.0-dev.N` as a **pre-release** with actual compiled files plus hashes. A failed build **must not** produce a flashable release.
* **Traceability:** `pm version` and the adjacent build-manifest JSON identify the exact source commit.

Version policy: increment `VERSION` for intentional feature/compatibility changes; CI run numbers disambiguate rebuilds of the same source revision. Pre-release means **not hardware-qualified**. Only upgrade to a stable `v1.0.0` after bench tests, 1-hour cumulative measurement comparison, unexpected-reset tests, and a successful recovery drill.

## Hardware verification before installing remotely

1. Confirm RAK4631 core identity and placement of RAK15001 in slot C; install and verify the exact-board OTAFIX bootloader **locally**.
2. Verify normal MeshCore radio operation on the bench before using experimental power-monitor images.
3. Use `pm version` and `pm sensors` over USB to confirm all three I2C devices and the desired firmware SHA.
4. Put a known load in series with INA219 `0x41`; measure bus voltage and peak TX current with a separate reference meter.
5. Observe four consecutive 15-minute packets and compare cumulative mWh/coverage against a calibrated power meter. Check wake/idle power penalty.
6. Check `ota self`, `ota status`, `ota qspi` on a matching OTA-enabled repeater. Expect RAK15001 JEDEC `C84015`, 2048 KiB, and a capable bootloader.
7. Test watchdog/reset/checkpoint behavior, reboots and power interruptions. Only then plan a remote deployment.

### Troubleshooting

* `solar40:MISSING`: check the generic INA219's A0/A1 address and I2C pull-ups; verify 3.3 V logic.
* `load41:MISSING`: RAK16000 must actually use `0x41`; verify I2C connection.
* `mcp18:MISSING`: MCP9808 should be `0x18`; check its A0/A1/A2 straps.
* 0 or incorrect energy: check series shunt wiring, direction and resistor value; do not confuse battery current with repeater consumption.
* `QSPI store:ERR`: recheck RAK15001 slot C, flash module identity, and exact bootloader pairing.
* Build failure: open GitHub Actions logs; do not flash an unverified artifact.
* `pm sensors` prints only on USB: remote MeshCore CLI integration is not implemented in this development version.

**Safety:** Solar charging is an electrical power-management function, not a regulated laboratory supply. Never insert current monitors between Li-ion battery terminals without appropriate insulation, current limits and short-circuit protection.

## References

* [Texas Instruments INA219](https://www.ti.com/product/INA219)
* [RAK16000 module](https://docs.rakwireless.com/product-categories/wisblock/rak16000/)
* [RAK4631 + RAK15001 OTAFIX pairing and QSPI support](https://github.com/Mesh-America/mesh-america-quake-repeater/blob/c908bb09e68ca81e1d19198776e0f2e5b7e48653/docs/ota_nrf52_qspi.md)
* [MeshCore upstream build configurations](https://github.com/Mesh-America/mesh-america-quake-repeater/blob/c908bb09e68ca81e1d19198776e0f2e5b7e48653/variants/rak4631/platformio.ini)
