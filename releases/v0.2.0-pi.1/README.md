# RAK4631 PowerMonitor 0.2.0-pi.1

**Historical Mesh-America fork build. For the official meshcore-dev/MeshCore
port without LoRa OTA, use version 0.3.0 or newer.**

**Native on-demand telemetry; no periodic power-monitor floods.**

Built on Raspberry Pi 5 / aarch64 Linux from clean source commit
`169b96e59ecb0e948e0c7ccdaf055e4234bca6a1`. Pinned MeshCore upstream:
`c908bb09e68ca81e1d19198776e0f2e5b7e48653`.

Target: RAK4631 + RAK15001 in slot C, with matching
**RAK4631_RAK15001_C OTAFIX** bootloader. Application images only; they do
not install a bootloader/SoftDevice. Not for RAK3401/RAK13302 1 W hardware.

## Read the stored statistics

Connect/login to the repeater with environment-telemetry access and refresh
the normal **Telemetry/Sensors** view in your MeshCore client. This is the
existing request/reply protocol, not a new broadcast or a scheduled report.

| Channel | Solar period |
| --- | --- |
| 110 | Rolling last 15 minutes |
| 111 | Rolling last hour |
| 112 | Today since 00:00 UTC |
| 113 | Yesterday, 00:00:00–23:59:59 UTC |

Each period provides generic **mWh**, analog-input **average W**, native
energy **kWh**, and measured coverage **%**. The generic and analog fields
preserve useful small-node precision; native energy resolves only 1 Wh and
native power only 1 W. Average power uses measured time; gaps are not zeroes.
Client labels/field support vary: see the root README's complete channel map.
Channels 100/101 provide solar/load instantaneous measurements and cumulative
energy, 102 outside temperature, and 114 snapshot-save status.

The authenticated admin console also supports `pm solar 15m`, `pm solar 1h`,
`pm solar today`, and `pm solar yesterday`. These are read-only on-demand
responses; counter reset is local USB only.

Energy is integrated from fast samples and kept in 10-second history buckets.
Rolling boundary resolution is up to 10 seconds, reflected in coverage.
UTC time must be valid. History and day counters are checkpointed in two
checksummed InternalFS files every 15 minutes and on day rollover; a power cut
can lose samples after the last checkpoint. No external OTA staging space is
used. Upgrading from 0.1.0 starts fresh version-3 snapshots.

## Validation and artifacts

Host tests passed for integration, signed power, timer wrap, rolling windows,
missing samples, restored history state, UTC midnight rollover, skipped days,
clock rollback, telemetry units and unsigned-field handling. The firmware
compiled and passed the upstream runtime-RAM and compiled DFU-handoff checks.
See `build.log` and `verification.json`.

BIN size: **551,124 bytes**, application base **0x26000**. Highest HEX address:
**0xAC8D3**, below the unchanged **0xED000** limit. UF2: **2,153 blocks**, family
**0xADA52840**. All three formats retain the final EndF/layout identity.
Hashes, sizes, embedded version/source and HEX/BIN/UF2 byte equivalence passed.
The manifest and `.sha256` file identify these exact artifacts.

Rebuild from the source commit with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-build.txt
bash tests/run_tests.sh
PM_BUILD_SUFFIX=pi.1 bash scripts/build_on_pi.sh rak15001
(cd output && sha256sum -c RAK4631_rak15001_PM_v0.2.0-pi.1.sha256)
```

Build-time identity data may prevent byte-identical rebuilds. No device was
flashed. Physical sensor accuracy, radio/client presentation, persistence
through real power interruption and OTA operation remain bench-test items.
