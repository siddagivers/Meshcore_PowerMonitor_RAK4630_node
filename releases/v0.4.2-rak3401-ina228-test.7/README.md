# RAK3401 + RAK13302 1 W Bluetooth DFU build

This MeshCore repeater application targets the RAK3401 core with the RAK13302
1 W radio. `pm version` reports `0.4.2-rak3401-ina228-test.7`. The source commit
is `a1cf90043430` and the MeshCore base is `81dbae592ffa`.

Run `start ota` in the repeater admin console. In the nRF Device Firmware
Update app, select the nearby RAK3401 DFU device and the ZIP as downloaded.
The application package uses Nordic/Adafruit legacy DFU 0.5 and expects the
board's S140 6.1.1 SoftDevice (`0x00B6`).

Power telemetry uses battery INA228 `0x40`, solar INA228 `0x41` and MCP9808
`0x18`, along with supported standard environmental sensors. It retains the
test.7 polling, telemetry memory and completed UTC-day history fixes. This
port uses the shared INA228 sensor profile. The older custom INA219/LTR390
UV sensor profile and experimental external-flash MeshCore OTA are separate
firmware features.

Rebuild on the Pi with:

```sh
PM_BOARD=rak3401 PM_INA228=1 PM_BUILD_SUFFIX=rak3401-ina228-test.7 \
  bash scripts/build_on_pi.sh official
```
