# PowerMonitor 0.4.2-ota-test.1

**Only matched to the exact normal OTAFIX 2.4.12 `wiscore_rak4631_auto` S140 6.1.1 bootloader.** Old 0.4.0/0.4.1 and dedicated-loader pairs must not be mixed with this set. Follow [the flashing order](../../docs/MATCHED_FLASHING_SET.md).

After the matched bootstrap is running, sign this test image with its JSON manifest in the Pi web uploader and transfer it over the mesh.

Run `ota test` after reconnecting:

```text
OTA update done - TEST2 | PM 0.4.2-ota-test.1 | git 58edb2355282
```

`pm ota boot` must show `hash=ec860fb46697ac4b handoff=52 match=1`. The application verifies the complete bootloader hash and its capabilities before pairing/activation; it selects RAK15001 CS P0.26 with source 0x52. No fallback to W25/internal/SD or bootloader update from this application.

Source 58edb2355282594883b02a68995bd94f54bd7bef; official MeshCore v1.18.0 base 81dbae592ffad40b4212bc0b37e82b38da08f4bc. Application bytes 380524 / 712704; static RAM 41944 / 235520 (runtime heap/stack additional). Application-only Legacy DFU 0.5 ZIP, SDreq B6. Manifest includes exact required bootloader SHA256, target and handoff.

Host integration/crypto/web tests and actual ARM compilation passed. The actual published bootloader payload passed the policy/capability test; wrong hashes, SDs and capabilities are rejected. SHA256, HEX/BIN/bounds, UF2 data/family/order, DFU application/BIN/CRC16/B6, embedded version/source and distinct BASELINE/TEST2 markers verified. Both real application images were signed with ephemeral test keys and accepted by the device C++ verifier. No production key was created or used, and no hardware was flashed by Codex. Physical bootloader upgrade and mesh install remain to be tested on the owner's board.
