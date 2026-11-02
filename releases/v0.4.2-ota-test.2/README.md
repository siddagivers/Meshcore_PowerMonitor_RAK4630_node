# PowerMonitor 0.4.2-ota-test.2

OTA test application for a receiver already running 0.4.2-bootstrap.2 with matching OTAFIX2.4.12 bootloader, RAK15001 slot C pairing and trusted firmware signing public key.

Download the application ZIP and matching JSON, select both in the Pi firmware uploader and verify/sign there. Uploading these files to the web page does not flash the receiver. The mesh transfer and activation are separate explicit actions. Keep bootstrap.2 installed as the starting receiver image for the OTA test.

After successful activation, `pm version` reports `0.4.2-ota-test.2 git 5f1430b`; `ota test` reports `OTA update done - TEST2 | PM 0.4.2-ota-test.2 | git 5f1430b`. This confirms the running image; use the transfer log to establish how it was installed.

Includes the software hash fix physically confirmed in bootstrap.2. Source commit 5f1430b. ARM build and package checks passed (manifest SHA256/sizes, HEX/BIN equality, UF2 family/order/range and embedded version/revision). BIN 380556 bytes. No mesh transmission, device flash or successful OTA activation was performed by Codex.
