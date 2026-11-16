# INA228 test.3 — telemetry reply size correction

Source dae1bbc35dc3. Battery 0x40, solar 0x41, R100. Includes the INA disable,
described help and timed radio commands from test.2; history format unchanged.

The pinned stock telemetry encoder allowed 180 bytes while its encrypted
datagram size guard only accepts 167 plaintext bytes including the four-byte
response tag. A filled history/environment response could therefore be
discarded before transmission and appear as `Telemetry request failed`.

This build limits Cayenne data to 163 bytes. All INA228 V/I/P/history/coverage
and age fields fit, with base battery voltage. Optional environmental fields
may be omitted when no room remains. Flooded requests that cannot combine
route and telemetry now return route information and data as separate replies.
All replies remain requested/authenticated; no periodic telemetry flood added.

Use the application UF2 or compatible app DFU ZIP. No bootloader change or
automatic flash. Existing identity/settings/history files are not modified
by this transport correction. After installation check `pm version` for
0.4.2-ina228-test.3 git dae1bbc35dc3, then request telemetry in the app.

Validation: actual ARM compile BIN394288; encrypted payload/padding boundary
tests; regression suite; HEX/BIN/UF2 family/address/order/bytes equivalence;
manifest hashes; Nordic application DFU CRC16/S140 B6; actual full-size package
accepted by the software verifier with a disposable signing key and tampered/
untrusted variants rejected. No production signing key or radio was used.
Physical app reception/direct and repeater routes still need testing. No
hardware flash was performed by Codex.
