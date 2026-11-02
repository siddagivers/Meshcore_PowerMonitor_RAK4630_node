# PowerMonitor 0.4.2-ota-test.3

Matching OTA test image for the bounded-I2C bootstrap.3 application. Both use the same pinned official MeshCore base, OTAFIX2.4.12/S1406.1.1 bootloader pairing and RAK15001 slot C target. The exact cause of the observed radio/USB stall is not yet proven. This image removes eight unbounded Wire driver waits and adds `pm diag` I2C timeout diagnostics; physical stall/transfer testing remains necessary.

Install bootstrap.3 locally first. Then download this ZIP plus its matching JSON, verify/sign on your Pi and start a fresh transfer. This is a different image/hash from ota-test.2 and cannot resume the old image's staged bytes. Do not activate the old ota-test.2 package, which would restore the old driver.

After activation, `ota test` reports `OTA update done - TEST3 | PM 0.4.2-ota-test.3 | git e4c0429`. `pm diag` reports I2C timeout counts and stages (reset at reboot).

Actual ARM build, ELF timeout symbols, BIN/HEX equivalence, UF2 family/order/bounds, manifest sizes/SHA256, application-only DFU ZIP/CRC16/S140 requirement and real-image disposable-key signing/device-verifier tests passed. BIN 381724 bytes, static RAM 41944 bytes. No physical flash or OTA activation performed by Codex.
