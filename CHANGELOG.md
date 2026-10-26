# Changelog

## 0.1.0 — development baseline (2026-10-26)

- New MeshCore RAK4631 repeater power sampler, based on pinned upstream.
- INA219 solar at 0x40 and load at 0x41; MCP9808 at 0x18.
- Configurable shunt resistances, current sign, 20ms target sampling, mWh integration and gap coverage.
- Solar/load day totals and 15-minute mesh text report.
- Internal LittleFS two-slot checkpoints; external RAK15001 stays with MeshCore mOTA.
- Versioned Raspberry Pi build helper and exact source-commit provenance.
- GitHub Actions compiles, uploads named artifacts, creates versioned pre-releases only on success.
- No claim of complete hardware validation; initial version is development-only.

Version conventions:

- VERSION contains major.minor.patch.
- GitHub Actions run N publishes (if successful) vMAJOR.MINOR.PATCH-dev.N.
- Each image embeds the same exact version and source git SHA, available via pm version.
- New code changes after release should bump VERSION as appropriate. Do not overwrite existing tags.
