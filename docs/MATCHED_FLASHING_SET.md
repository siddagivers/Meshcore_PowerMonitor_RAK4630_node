# Matched local flashing set: OTAFIX 2.4.12 + PowerMonitor 0.4.2

For the reported **RAK4630/RAK4631 + RAK15001 in slot C**, currently running the ordinary `0.9.2-OTAFIX2.2-BP1.3` RAK4631 bootloader and S140 6.1.1. The old loader supports Bluetooth DFU, not the external-flash mOTA handoff used by this project.

## Download these two files for local installation

1. **Bootloader + SoftDevice ZIP (official upstream file):**
   [wiscore_rak4631_auto_bootloader-v0.11.0-OTAFIX2.4.12_s140_6.1.1.zip](https://github.com/mikecarper/Adafruit_nRF52_Bootloader_OTAFIX/releases/download/v0.11.0-OTAFIX2.4.12/wiscore_rak4631_auto_bootloader-v0.11.0-OTAFIX2.4.12_s140_6.1.1.zip)
2. **Matched bootstrap application ZIP:**
   [RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.1.zip](../releases/v0.4.2-bootstrap.1/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-bootstrap.1.zip)

Select these individual ZIP files directly in a Nordic/Adafruit **Legacy DFU 0.5** uploader supporting bootloader/SoftDevice packages. They are not ZIPs to extract/copy onto the UF2 drive. The first package is a bootloader/SoftDevice update; the second is application-only. No erase firmware or RAK3401/recovery image is part of this set.

## Flashing order

1. Save your current settings and recovery application before changing the bootloader. Keep the board accessible and powered throughout each DFU operation.
2. Enter the installed bootloader's supported BLE or serial DFU mode. Install the **bootloader ZIP first**. This combined package contains S140 **6.1.1** and the normal RAK4631 auto OTAFIX **2.4.12** bootloader. Do not use a plain application-only updater that cannot handle a combined package.
3. Reconnect/rescan after the bootloader restarts. The normal BLE identity is `4631_DFU`; the address may change. If USB is configured by a computer the loader may expose its UF2/serial interface instead of immediately advertising BLE. Use the board's supported entry method for the transport you intend to use.
4. Install the **0.4.2-bootstrap.1 application ZIP second**. The combined bootloader update requires an application reinstall. Do not reinstall old 0.4.0/0.4.1 applications: their RAK15001 handoff is not matched to the new unified loader.
5. Check `INFO_UF2.TXT` for OTAFIX **2.4.12**, RAK4631 and S140 **6.1.1**. Boot normally and use the local USB application console:

   ```text
   pm version
   pm ota boot
   pm ota status
   ```

   The application version must be `0.4.2-bootstrap.1`. The boot diagnostic must include `sd=00b6`, `hash=ec860fb46697ac4b`, `handoff=52`, `match=1`. Status must report `boot=1 flash=2097152`; `pair=0` before provisioning is expected.
6. On the Pi web page, create a signing key if none exists. Use its **firmware signing public key**, not a radio identity key, in the target's local USB console:

   ```text
   pm ota trust <signing-public-key-from-Pi-page>
   pm ota pair RAK4631_RAK15001_C
   pm ota status
   ```

   Expect `pair=1 boot=1 flash=2097152`. These commands do not accept a radio/phone-admin console. If a gate fails, read `pm ota boot`; no force/bypass is provided.

## Separate image for the subsequent LoRa test

Once the local bootstrap is running, prepare the **0.4.2-ota-test.1** ZIP (or BIN) and matching JSON in the Pi web uploader:

- [OTA test ZIP](../releases/v0.4.2-ota-test.1/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-ota-test.1.zip)
- [Matching JSON](../releases/v0.4.2-ota-test.1/RAK4631_official_rak15001_lora_ota_PM_v0.4.2-ota-test.1.json)

Sign on the Pi, send through the companion and learned MeshCore route, and explicitly activate after verification. The bootstrap's `ota test` reply says **BASELINE**. After installing the test variant over the mesh, the same command says:

```text
OTA update done - TEST2 | PM 0.4.2-ota-test.1 | git <source revision>
```

Help lists `ota test`, `pm ota test` and `pm ota boot`. The marker identifies the running image, not independently how it was installed; use the transfer log and returned version together.

## Exact pairing and verification

- Official bootloader release: [v0.11.0-OTAFIX2.4.12](https://github.com/mikecarper/Adafruit_nRF52_Bootloader_OTAFIX/releases/tag/v0.11.0-OTAFIX2.4.12).
- Official combined ZIP SHA256: `0a7d556cbe68f9698c20ce3e892d1f39a6fc08f1cfb178df7128b340f9f8dc35`.
- Its exact 40,960-byte bootloader payload SHA256: `ec860fb46697ac4b458f4b961dec69b428380be1ce31a226cff60298f3281545`.
- Normal published image only; the application also requires format-2/FULL capability, QSPI storage capability and runtime S140 FWID B6. The firmware hashes the actual bootloader flash once per boot and refuses unknown/recovery/altered loaders.
- The bootloader's published `MOTABLDR` record is ABI 3, codec mask `0x0005`, primary storage `0x0A`; its authenticated-layout-adjacent `MOTASTOR` record advertises optional NOR `0x14`. The application parser resolves storage to `0x1E` and selects RAK15001 with **GPREGRET2=0x52**. The loader's other NOR selector `0x51` uses CS P0.31 and is not used for this module. Verified directly against the published binary and tagged source `src/ota_qspi.c`.
- The new application/host tools use target `RAK4631_PM_RAK15001_C_OTAFIX2412`. Old-target signed packages and old-profile build manifests are rejected instead of accidentally restoring an incompatible receiver.
- Application start/limit remain `0x26000..<0xD4000`; InternalFS layout, sensor wiring and radio configuration are unchanged. The application does not update a bootloader itself.

The published ZIP checksum, combined payload size/CRC16, capability records, bootloader hash and exact application profile policy were checked on the Pi. Application compilation and software package tests do not constitute a physical bootloader upgrade, over-radio install, power-cut qualification or proof of preserved settings on this individual board. No board was flashed by Codex.

The bootloader UF2 updater in this release requires valid hash-bound application EndF metadata. The old application installed over Bluetooth did not include that trailer, so this set intentionally uses the combined **Legacy DFU ZIP**, not the `_mbr.uf2` updater. Your ordinary RAK4631 2.2 identity is not a historical `4631_AUTO_DFU` recovery identity; no `R_` recovery bridge is included or recommended here.
