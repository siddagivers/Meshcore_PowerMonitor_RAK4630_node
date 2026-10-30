# PowerMonitor 0.4.0-pi.ota.1

Optional signed LoRa OTA receiver for RAK15001 slot C + the matching OTAFIX bootloader. Direct and multihop transfers use authenticated MeshCore admin messages. Requires one local receiver install and local USB signer/pairing provisioning; see [the complete setup guide](../../docs/LORA_OTA.md). Use the ZIP directly for initial phone DFU. Future LoRa updates use a signed .mota created by scripts/lora_ota.py, not this ZIP.

Compiled from source **8c213b910826dfd9b1737556ddd62c6dbc083bf5** on Raspberry Pi. Official MeshCore v1.18.0 base **81dbae592ffad40b4212bc0b37e82b38da08f4bc**. Application BIN **379660 / 712704 bytes**, static RAM **41896 / 235520 bytes**. Static RAM excludes runtime heap/stack; OTA staging allocates additional heap on demand.

The application-only DFU ZIP is Nordic/Adafruit legacy DFU 0.5 for existing S140 v6.1.1 / SDreq 0x00B6. No bootloader/SoftDevice is installed. Application remains below 0xD4000; existing power counters/history and signed current presentation remain supported.

Validation passed: integrator/sensor/solar history/UTC tests; signed-current and OTA transfer bounds/retry tests; package signing/inspection with ephemeral test keys; actual device C++ streaming verifier (bad signatures, unknown signers, damaged payloads/leaves and truncation); simulated uploader lost replies; real compiled image package checked against the pinned reference motalib parser. Both optional and default ARM builds passed. Image SHA256, HEX/BIN equality, UF2 addresses/family/data and DFU BIN/CRC16/SoftDevice requirement passed; binary receiver-profile isolation checked. See build.log and the verification JSON.

**No device was flashed by Codex. Actual direct/multihop LoRa transfer, OTAFIX application installation, flash power-interruption recovery and phone/client behavior are not hardware-qualified by these software tests.** No production signing key or signed production .mota is shipped: the operator owns and provisions that key locally.
