# INA219 test.1

Source 068baa248538. Legacy INA219 profile: solar 0x40, battery/load 0x41;
MCP9808 handling remains independent. Do not use this on INA228 hardware.

Adds saved `pm ina off` / `pm ina on`, described `pm help 1..12`, and
separate timed `radio off 40`, `radio on`, `radio status`, `radio help`.
Shutdown requests stop INA polling/retries and preserve history; they do not
disconnect module power. Help explains all PM options and USB-only operations.
Radio pauses after >=10 seconds/queue+TX drain, resumes after the specified
duration, and cancels if traffic has not drained in 60 seconds. USB and sensors
remain active. A paused radio cannot receive early-resume commands over LoRa.

See [command descriptions](../../docs/PM_COMMANDS.md). Existing recovery.5
sensor retry and snapshot fixes remain included. Five-minute battery mode and
adaptive solar monitoring belong to the separate INA228 profile.

BIN393896 bytes. Actual ARM compilation, app-only DFU CRC/S140 B6, manifest
hashes, HEX/BIN/UF2 layout and full-size signed-package software verification
passed. Native persistence failure/help-length/radio timer/legacy firmware
tests passed. Hardware shutdown and RF pause/resume still require testing.
UF2 and app DFU ZIP are included; no bootloader or automatic flashing.
