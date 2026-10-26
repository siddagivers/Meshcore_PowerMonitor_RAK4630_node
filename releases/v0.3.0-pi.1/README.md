# RAK4631 PowerMonitor 0.3.0-pi.1 — official MeshCore base

**Official meshcore-dev/MeshCore v1.18.0-based repeater, with power monitoring,
native sensors and on-demand telemetry. No LoRa OTA updates.**

- Official upstream: [meshcore-dev/MeshCore](https://github.com/meshcore-dev/MeshCore),
  pinned to `81dbae592ffad40b4212bc0b37e82b38da08f4bc`.
- Local source: `df949d492f9e5ffcdaf4211165d900e074026238`.
- Local version: `0.3.0-pi.1`; upstream's firmware version remains `v1.18.0`.
- Built from clean tracked source on Raspberry Pi 5 / aarch64 Linux.
- Base: official `RAK_4631_repeater`; overlay: `RAK_4631_repeater_power_monitor`.
- Target: nRF52840 RAK4631, standard S140 v6.1.1 board profile.
  Not RAK3401/RAK13302 1 W hardware.

## Power and sensors

Dual INA219 at `0x40` (solar) and `0x41` (series-connected load), MCP9808 at
`0x18`, and the official RAK4631 environmental-sensor/GPS support are retained.
Stock INA260 is disabled to avoid the `0x41` conflict; a compiler guard enforces
that exclusion. BME680/BSEC and other ordinary official RAK sensors remain
inherited. No external RAK15001 flash driver is added or used.

Connect/login to the repeater with environment-telemetry access and refresh
the client's native **Telemetry/Sensors** view. The power monitor sends no
scheduled flood messages or unsolicited power reports.

| Channel | Reading |
| --- | --- |
| 100 / 101 | Solar / load instantaneous voltage, current, signed analog W and cumulative energy |
| 102 | MCP9808 outside temperature |
| 110 | Solar rolling last 15 minutes |
| 111 | Solar rolling last hour |
| 112 | Solar today since 00:00 UTC |
| 113 | Solar yesterday, completed 00:00:00–23:59:59 UTC day |
| 114 | Snapshot checkpoint status |

Each solar period provides generic **mWh**, analog **average W**, native energy
**kWh**, and measured coverage **%**. Generic/analog fields retain useful
precision: standard LPP energy resolves only 1 Wh and standard power 1 W.
Average power uses measured time, with gaps reported separately. Client labels
and field support vary; no client UI change has been bench-tested.

The authenticated admin console provides read-only `pm solar 15m`,
`pm solar 1h`, `pm solar today`, `pm solar yesterday`, `pm sensors` and
`pm version` diagnostics. Counter reset remains local USB only, even when a
remote admin supplies a zero timestamp.

Solar histories use 10-second buckets; rolling boundary resolution is up to
10 seconds and missing time reduces coverage. Valid UTC time is required.
History/day counters are checkpointed to alternating checksummed InternalFS
files every 15 minutes and on day rollover. Sudden power loss can lose samples
after the last checkpoint. No external OTA staging storage is used.

## Size and validation

| Resource | Build limit | Final use |
| --- | --- | --- |
| Application flash | 712,704 bytes / 696 KiB | **365,936 bytes / 51.3%** |
| Static SRAM against board budget | 235,520 bytes / 230 KiB | **41,808 bytes / 17.8%** |

The physical nRF52840 has 1 MiB flash and 256 KiB RAM; reserved regions reduce
the build budgets above. Heap and task stacks consume additional runtime RAM
and are not fully represented by the static-SRAM figure.

HEX starts at **0x26000**, ends at **0x7F56F**, and remains below the protected
**0xD4000** application limit. UF2 has **1,430 blocks**, family **0xADA52840**.
BIN size is **365,936 bytes**. Images are application-only; no custom EndF
trailer, OTAFIX patch, LoRa OTA package, bootloader or SoftDevice is included.
The official ExtraFS-safe linker script preserves filesystem reservations.

Host integration/history tests and official PlatformIO compilation passed.
Hashes, image sizes, official upstream identity, embedded local source/version,
address limits and HEX/BIN/UF2 equivalence passed; see `verification.json` and
`build.log`. Hashes were also checked after copying the images locally. Compiled
reset code was inspected to confirm history is cleared in place without a
multi-kilobyte stack temporary. Fork-specific DFU/runtime-RAM checks are not
part of this official-source build.

No device was flashed. Sensor accuracy, radio/client presentation, peak runtime
RAM, persistence through actual power loss and USB recovery need local bench
tests. If the board previously used a custom bootloader, verify its existing
bootloader/SoftDevice compatibility locally; these files cannot migrate it.

## Rebuild

Check out the local source commit above, then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
bash tests/run_tests.sh
PM_BUILD_SUFFIX=pi.1 bash scripts/build_on_pi.sh official
(cd output && sha256sum -c RAK4631_official_no_lora_ota_PM_v0.3.0-pi.1.sha256)
```

Build-time data can prevent byte-identical rebuilds. Do not use these files
with the old Mesh-America fork's LoRa OTA commands. Future OTA can support
both direct radio links and multihop routes, but it is outside this profile.
