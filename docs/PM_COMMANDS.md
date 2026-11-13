# PowerMonitor commands: INA228 test.2 / INA219 test.1

`pm help` displays the index; `pm help 1` through `pm help 12` display all
described pages. Each page fits a MeshCore admin reply without truncation.
The same commands work locally over USB and in authenticated Repeater Admin,
except operations specifically marked USB only.

## Disable power sensors

`pm ina off` requests shutdown of both power sensors, invalidates live readings,
stops automatic sampling/re-detection, and saves the disabled flag for reboot.
`pm ina on` re-detects and resumes the configured profile. `pm sensors` reports
DISABLED while off. Historical data is retained; gaps are not zero consumption.

Both firmware profiles use the same `/pm-ina.enable` flag. INA219 firmware
controls INA219 devices; INA228 firmware controls INA228 devices. These are
separate builds, not automatic sensor-type detection. INA228's five-minute
battery mode remains a separate setting and cannot be changed while disabled.

This does not electrically disconnect 3.3 V or the battery. At startup the
firmware makes one identification/configuration pass to request shutdown of
connected sensors, then stops automatic access. A sensor attached or power-cycled
after that may start in its hardware default mode; software cannot guarantee
its power state without talking to it or controlling its supply. Shutdown and
persistence failures are reported in the command reply. MCP/environmental
sensors remain independent. INA219 `pm i2c` skips 0x40/0x41 while disabled.

## Shared commands

| Command | Description |
|---|---|
| `pm version` | Firmware version/source revision |
| `pm diag` | I2C timeouts and uptime |
| `pm sensors` | Sensor detection, mode and failures |
| `pm solar` | Latest solar V/A/W |
| `pm load` | Latest battery V/A/W |
| `pm channels` | Telemetry channel/unit legend |
| `pm ina on` / `pm ina off` | Persistent INA enable/disable |
| `pm ota status` | Pairing, flash and staged image progress |
| `pm ota boot` | Exact bootloader compatibility |
| `pm ota result` | Last verification/activation result |
| `pm ota verify <id>` | Verify the staged package |
| `pm ota apply <id>` | Verify and explicitly activate/reset |
| `pm ota cancel` | Discard staged package |
| `pm ota pair RAK4631_RAK15001_C` | Confirm hardware pairing, USB only |
| `pm ota trust <signer-public-key>` | Provision signing trust, USB only |
| `pm ota test` / `ota test` | Running firmware marker |
| `pm ota begin ...` / `pm ota data ...` | Low-level uploader protocol; use uploader |
| `pm ota help` | OTA protocol command summary |

## INA228-only commands

| Command | Description |
|---|---|
| `pm status` | Same sensor/mode summary as pm sensors |
| `pm battery continuous on` | Continuous battery conversions |
| `pm battery continuous off` | Five-minute single-shot battery sampling |
| `pm history solar 5m` | Solar observed mean V/A/W; also 15m, 1h, day |
| `pm history battery 5m` | Battery observed mean V/A/W; also 15m, 1h, day |

Day means the current UTC calendar day. Percentages indicate measured
coverage, and sparse readings do not measure sleep gaps. See INA228_TEST.md.

## INA219-only commands

| Command | Description |
|---|---|
| `pm` / `pm status` | Power/energy summary |
| `pm day` | UTC energy totals and restore count |
| `pm info` | Shunt values, addresses and version |
| `pm solar 15m` / `1h` / `today` / `yesterday` | Solar energy/power/coverage |
| `pm temp` | MCP9808 reading and ID diagnostics |
| `pm i2c` | Explicit address scan |
| `pm reset YES` | Clear energy/history, USB only |

## Radio commands are separate

`get radio` inspects settings; `set radio <MHz>,<kHz>,<SF>,<CR>` saves new
settings and requires `reboot` to apply. `reboot` restarts the entire device.

These builds add `radio off <seconds>` independently of PM commands. For
example `radio off 40` waits at least ten seconds for the acknowledgment and
pending traffic/TX to drain, then places the radio in warm sleep and skips
MeshCore packet processing for forty seconds. It automatically resumes RX
after the requested duration. If traffic does not drain within sixty seconds,
the pause is cancelled; inspect `radio status` rather than assuming it started.

`radio off` without a number defaults to 180 seconds; valid durations are
1–86400 seconds. `radio on` cancels a scheduled pause or resumes early.
`radio status` reports state; `radio help` describes these commands. During
the pause no LoRa command can arrive: early resume requires local USB.
USB CLI and sensor sampling continue. A reboot restores radio operation;
the pause is not persisted. Radio sleep/resume errors are reported by status.
No frequency, modulation, identity, password or bootloader setting is changed.
