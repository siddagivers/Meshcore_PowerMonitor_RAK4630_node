# RAK4631 INA228 test.8 for SK-RK-Sidorovo

The Sidorovo wiring uses solar INA228 at `0x40` and battery INA228 at `0x41`.
Solar still reports on channels 100 and 110–113. Battery still reports on
channels 101 and 120–123. The power page is selected at boot for the Pi's
scheduled telemetry collection. Old history snapshots remain separate from
the new measurements.

Use the UF2 for USB flashing. For MeshCore OTA, select the matching ZIP and
JSON in the Pi uploader. The ZIP also supports Bluetooth DFU on the compatible
RAK4631 bootloader. After install, `pm version` should report
`0.4.2-ina228-test.8-sidorovo`. Run `pm sensors` to check `solar40` and `battery41`.

Source commit `1b0807ddfad8`. Rebuild with:

```sh
PM_INA228=1 PM_SIDOROVO=1 PM_BUILD_SUFFIX=ina228-test.8-sidorovo \
  bash scripts/build_on_pi.sh official-lora-ota
```
