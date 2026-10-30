# PowerMonitor 0.3.2-pi.1

Use `RAK4631_official_no_lora_ota_PM_v0.3.2-pi.1.zip` directly with the same phone DFU uploader and existing bootloader pairing used for 0.3.1. This is an application-only Nordic/Adafruit legacy DFU 0.5 ZIP for S140 v6.1.1 (SD requirement 0x00B6). No bootloader/SoftDevice change or LoRa OTA support.

- Solar channel 100 transmits signed Current, including zero/reverse flow.
- Battery channel 101 Current and Analog Input watts: positive charging, negative discharging, for the previously tested wiring.
- Native Power is unsigned and displays magnitude in both directions. Analog Input is signed watts. Current is signed amperes, with 1 mA wire resolution.
- Removes digital indicators on 100/101/102/114. Failed samples are omitted; use `pm sensors`, `pm solar`, `pm load` for diagnostics. `pm solar 15m` includes checkpoint status.
- Existing cumulative battery energy remains discharge-positive; saved histories/counters are preserved. Instantaneous sign changes do not rewrite historical energy.

Compiled on Raspberry Pi from source e90ef78b1cc577b155264dc8b42248e45627aa0c, official MeshCore 81dbae592ffad40b4212bc0b37e82b38da08f4bc (v1.18.0). BIN 366592 bytes / 712704 application limit; static RAM 41808 / 235520 bytes. Runtime stack/heap are not fully represented by static RAM.

Validation: integrator, solar history/UTC/persistence, sensor decode and instantaneous telemetry regression tests passed. Exact installed CayenneLPP wire encoding verified: -9 mA = FFF7 and +265 mA = 0109. ARM build passed; DFU application/CRC16/SD requirement/BIN equivalence passed. Manifest SHA256, HEX/BIN and UF2 address/family/data equivalence passed (verification.json). Build log included. No device flashed by Codex; official phone-client display and physical charging/discharging with this build still require validation. Refresh telemetry after updating to clear cached fields.
