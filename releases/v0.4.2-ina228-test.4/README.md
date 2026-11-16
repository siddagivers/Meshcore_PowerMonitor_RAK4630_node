# INA228 test.4 — live, power-history and environment telemetry pages

Compiled source 8640d48158a2. Battery INA228 0x40, solar INA228 0x41, R100.
All previous sensor sampling, shutdown and timed-radio commands remain.

Select a page in Repeater Admin, then refresh the app's Telemetry screen:

| Command | Contents |
|---|---|
| `pm telemetry live` | Latest INA readings/ages + supported stock environmental sensors/MCU temperature; reboot default |
| `pm telemetry power` | Latest INA readings + all 5m/15m/1h/current UTC-day INA histories, ages and coverage |
| `pm telemetry environment` | Supported stock environment sensors/MCU temperature without INA history |
| `pm telemetry status` | Current selection |

Base board battery voltage is included in every page. Measurements and history
logging continue independently of page selection. The selection applies globally
to subsequent requests from all clients until changed; reboot resets it to live.
No flash write is made for page changes. `pm help 13` describes the controls.
The stock app receives one page per refresh: it is not required to merge several
packets into one telemetry record. MCP9808 exclusion in this INA228 test profile
is unchanged. All responses retain the 163-byte encrypted-safe Cayenne budget.

Environmental sensor safeguards: prior bounded Wire/AHT/SHT paths remain.
The installed BME280 driver already bounds forced measurement completion;
its remaining startup calibration-busy loop is now capped at 500 ms.

BIN395168 bytes. Actual ARM compilation, DFU CRC16/S140 B6, HEX/BIN and UF2
family/address/order/byte equivalence, hashes and signed full-size package
verification passed. Native tests cover page selection, input validation,
help lengths, encrypted payload boundaries, stuck sensor/recovery paths and
the existing power/history/OTA regressions. Signing tests use disposable keys.
Physical app reception, sensor accuracy, RF pause and long-term behavior still
require hardware testing. No device was flashed by Codex.

Use the UF2 locally or a compatible application DFU uploader with the ZIP.
No bootloader replacement is included. Existing identity/settings/history
formats are unchanged. This change does not add previous-day retention.
