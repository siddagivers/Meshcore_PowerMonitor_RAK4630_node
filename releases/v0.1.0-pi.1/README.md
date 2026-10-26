# RAK4631 PowerMonitor 0.1.0-pi.1

Built on a Raspberry Pi 5 (aarch64 Linux) from clean tracked source commit
`47a6413783894173cc5e4ab9b0a6f51d6ff79de5`, with pinned MeshCore upstream
`c908bb09e68ca81e1d19198776e0f2e5b7e48653`.

Target: `RAK_4631_repeater_power_monitor`, **RAK4631 + RAK15001 in slot C**.
Requires the matching `RAK4631_RAK15001_C` OTAFIX bootloader/storage pairing.
These application files do not install or replace a bootloader or SoftDevice.
Do not use them on the RAK3401 + RAK13302 1 W board.

## Files and verification

The manifest JSON records UTC build time, byte sizes, exact source revisions
and SHA-256 hashes. Check the `.sha256` file before use. The raw BIN is
549,016 bytes and starts at address **0x26000**. HEX and UF2 carry addresses.
The highest HEX byte is **0xAC097**, below the unchanged **0xED000** limit.
All three images include the upstream EndF/layout identity.

`verification.json` records successful checks of hashes, HEX/BIN exact
equivalence, UF2 family/address/block validation and byte equivalence with HEX,
and embedded `0.1.0-pi.1` / `47a641378389` version strings. Hashes were also
rechecked after copying the files from the Pi to the local checkout.
`build.log` records successful compilation, image generation, runtime RAM
budget and compiled Bluetooth DFU-handoff checks.

The host integration tests passed for constant load, a simulated TX burst,
sampling gaps, negative power and millis wrap. No device was flashed, and no
physical radio, dual-INA219, MCP9808, persistence or OTA test was performed.
These are experimental development artifacts, not hardware-qualified releases.

## Rebuild

Check out the source commit above, create/activate the Python venv, install
`requirements-build.txt`, then run:

```bash
bash tests/run_tests.sh
PM_BUILD_SUFFIX=pi.1 bash scripts/build_on_pi.sh rak15001
(cd output && sha256sum -c RAK4631_rak15001_PM_v0.1.0-pi.1.sha256)
```

This reproduces the build procedure, not necessarily byte-identical output:
the upstream identity/build tooling can include build-time information.
See the root README for wiring, calibration, limitations and bench checks.
