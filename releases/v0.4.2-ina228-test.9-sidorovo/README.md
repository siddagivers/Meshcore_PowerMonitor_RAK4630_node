# RAK4631 Sidorovo combined telemetry

Test.9 starts in the Combined view. It includes channel 1 (board voltage and
temperature), channel 2 (first detected environmental sensor), and the latest
and historical INA228 readings in the same telemetry reply. Solar remains at
I²C `0x40` and battery at `0x41`.

Select this view again with `pm telemetry combined` and refresh Telemetry in
MeshCore. Combined reserves space for the measurements by leaving sample age
and observed coverage to the dedicated `pm telemetry power` view. Missing
measurements are omitted. The Pi's Sidorovo collector converts INA current
and power to mA and mW for Domoticz.

Use the UF2 for USB flashing or the matching ZIP and JSON for MeshCore OTA.
After installing, `pm version` should report `0.4.2-ina228-test.9-sidorovo`.

Built from source commit `aa3d6fc5bd61` with:

```sh
PM_INA228=1 PM_SIDOROVO=1 PM_BUILD_SUFFIX=ina228-test.9-sidorovo \
  bash scripts/build_on_pi.sh official-lora-ota
```
