# PowerMonitor 0.4.2-bootstrap.3

Diagnostic/hardening build for a repeater that stopped responding over both LoRa and USB during OTA staging. The exact cause is not yet established. One concrete risk found in the original Adafruit nRF52 Wire driver was eight unbounded hardware-event waits. This build replaces those with 50 ms deadlines and an independent spin limit, plus bounded peripheral stop/re-enable recovery. The project-local Wire copy retains its original LGPL notices; the installed shared framework is not changed. Original RAK build/link hooks remain enabled.

Install the application UF2 through the existing USB bootloader drive. No bootloader update is required. After restart run:

```
pm version
pm diag
pm ota status
```

Expected version: 0.4.2-bootstrap.3 git 9346507. `pm diag` reports I2C timeout count and the last timeout stage. These counters reset at reboot. USB/LoRa recovery and full physical OTA transfer still need hardware validation. If the node becomes unresponsive again, this change has not fixed the whole problem.

Use the matching ota-test.3 package for subsequent activation testing. The old ota-test.2 image does not contain these bounded sensor waits and would restore the old driver if activated. A different signed image starts a fresh upload; it cannot reuse the old image's data as a verified new package.

Validation: ready/timeout/frozen-clock/clock-rollover host tests passed; all eight original driver waits patched, unexpected source rejected, reproducible local generation and unchanged framework verified; actual ARM compile and ELF timeout diagnostic symbols passed; BIN/HEX equivalence, UF2 family/order/range, manifest sizes/SHA256 and Nordic app-only DFU CRC16/S140 0x00B6 passed. BIN 381740 bytes, static RAM 41944/235520. No device flashed by Codex.
