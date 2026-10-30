# LoRa updates through the MeshCore network (experimental)

**Current 0.4.2 pairing:** exact normal OTAFIX 2.4.12 `wiscore_rak4631_auto`, S140 6.1.1; RAK15001 slot C; handoff 0x52. Follow [the matched flashing set](MATCHED_FLASHING_SET.md). The older dedicated-bootloader 0.4.0/0.4.1 packages are historical and are not compatible with this new pairing.

The optional **official-lora-ota** profile keeps the pinned official MeshCore v1.18.0 base and the power monitor. It adds a targeted, authenticated admin-CLI file transfer called **CLI1**. Ordinary MeshCore repeaters forward the encrypted admin messages using their existing routing; they do not need this receiver firmware. A direct link with a zero-length path works too. This is not the Mesh-America `PAYLOAD_TYPE_OTA` distribution protocol, and `motatool serve` is not its uploader. There are no periodic OTA advertisements or unsolicited firmware broadcasts.

The ordinary **official** profile remains available without LoRa OTA. Never use a no-OTA artifact as a remotely managed receiver if you need to preserve this feature.

## Hardware and first installation

This profile is ONLY for a RAK4630/RAK4631 nRF52840 on the compatible WisBlock base, **RAK15001 in slot C**, exact GD25Q16C JEDEC **C8 40 15**, and the exact published normal **OTAFIX 2.4.12 wiscore_rak4631_auto / S140 6.1.1 bootloader**. The application does not support RAK3401/RAK13302, W25Q16 or internal/SD fallback. It selects only RAK15001 on the unified bootloader; no other storage backend is chosen. No bootloader or SoftDevice is distributed or updated by this feature.

The flash module uses standard SPI through the QSPI peripheral in single-data-line mode. Mapping: Arduino SCK=3, CS=26, MOSI=30, MISO=29; IO2/IO3 disconnected; 8 MHz. Do not share its SPI chip-select with Ethernet, SD or another SPI module. Keep existing slot conflicts, including GNSS placement, consistent with the RAK15001 slot C pairing.

One local application update is required: existing 0.3.x cannot receive a firmware image over LoRa. Install the optional profile's application-only DFU ZIP using the same compatible phone DFU uploader/bootloader pairing. S140 v6.1.1, firmware ID **0x00B6**, application base **0x26000**, limit **0xD4000**, InternalFS reservations unchanged. The firmware neither replaces a bootloader nor silently switches storage layouts. An OTAFIX label alone does not prove the right storage profile. Confirm that the locally installed bootloader is the exact published normal 2.4.12 build before pairing.

## One-time local provisioning

Install host tools on the Pi or another computer (no live radio is opened by these commands):

```sh
python3 -m venv .ota-tools-venv
. .ota-tools-venv/bin/activate
pip install -r requirements-ota.txt
mkdir -p .keys
python scripts/lora_ota.py keygen .keys/power-monitor.pem
```

The tool prints the **public** signing key. Keep the private PEM file private and backed up; it is ignored by Git and never included in a firmware artifact. The tool refuses to overwrite an existing key.

With the target connected to **local USB serial**, run:

```text
pm ota trust <64-hex-character-public-signing-key>
pm ota pair RAK4631_RAK15001_C
pm ota status
```

Provisioning is deliberately rejected through radio admin commands, including packets with zero timestamps. Pairing checks the complete installed 40-KiB bootloader SHA256 against the published image, QSPI/full-image format-2 support, the running SoftDevice ID is B6 and the module responds with the exact flash identity/capacity. The local pairing command records the operator's confirmation of the physical slot and exact bootloader build; capability flags alone cannot identify its pin wiring. This is the only required local provisioning; subsequent application updates can travel through LoRa.

`pm ota status` should include `pair=1 boot=1 flash=2097152`. A failed gate does not have a force/ignore option. `boot=0` means this bootloader/SoftDevice combination is unsupported; resolve the pairing locally rather than trying to apply an image.

## Build, sign and transfer

Build on the Pi with the existing PlatformIO environment:

```sh
. .venv/bin/activate
PM_BUILD_SUFFIX=pi.ota.1 bash scripts/build_on_pi.sh official-lora-ota
```

Artifacts use the distinctive prefix `RAK4631_official_rak15001_lora_ota_PM_v...`; their JSON manifest states `lora_ota: true` and the exact storage profile. The ordinary profile uses `official_no_lora_ota` in its artifact name. Both produce a real application-only DFU ZIP for the initial local install/recovery.

Create a signed full-image `.mota` using the matching optional-profile BIN and JSON manifest:

```sh
python scripts/lora_ota.py pack output/NAME.bin output/NAME.json .keys/power-monitor.pem update.mota
python scripts/lora_ota.py inspect update.mota
```

The tool checks the BIN against the build manifest before signing. It appends a 56-byte EndF identity trailer to the compiled BIN, so the remotely installed image is that exact BIN plus the trailer. It uses a distinct `RAK4631_PM_RAK15001_C_OTAFIX2412` target ID and `RAK4631_RAK15001_C` hardware identity. It never packages or writes a bootloader. Do not upload the phone DFU ZIP through CLI1; the remote format is the signed `.mota` produced by this tool.

Connect a **companion radio** to the Pi/computer. This USB connection is to the local radio, not a cable to the remote repeater. Have the exact destination public key and an already learned direct or multihop route in the companion contacts. The uploader refuses an unknown/flood route, does not clear routes and never uses automatic flood fallback.

```sh
python scripts/lora_ota.py upload update.mota --port /dev/ttyACM0 --target <exact-64-hex-target-public-key>
```

The uploader prompts for the repeater admin password without echoing or storing it. It sends one 40-byte chunk at a time, waits for a correlated reply from the target, paces requests and bounds retries. A transfer failure stops; rerun the same command/file to resume from the target's saved position. A different image starts a new transfer. Route changes should be learned through the ordinary client before retrying.

By default this only **stages and verifies**. For installation use an explicit authenticated repeater admin command:

```text
pm ota apply <first-8-hex-characters-of-container-SHA256>
```

Alternatively add `--apply` to the upload command when you intend to install after verification. No hardware update is triggered by building, signing, inspection or ordinary staging. The receiver verifies again, then waits at least ten seconds for its reply, outgoing queue and in-flight transmission to drain. A queue blocked for a minute cancels the reset attempt. `pm ota cancel` cancels a pending activation and invalidates the staged container. A failed power-monitor checkpoint aborts activation before approval. `pm ota result` explains an aborted activation in the current boot. After reconnecting, check `pm version`: an activation acknowledgment is not proof the bootloader installed the image.

The official phone app has no upload button for this custom transport. Its authenticated Repeater Admin console can inspect `pm ota status`, request verification/activation or cancel; use this Python uploader plus a companion for file transfer.

## Verification, persistence and limitations

- Authentication remains upstream's admin-only command gate. Chunks carry session identity, exact offsets and bounded lengths; wrong/out-of-order/conflicting retries are rejected. Exact retries are idempotent.
- Received data stays in the external flash. No live application, SoftDevice or bootloader page is written by the transfer receiver. Two checksummed InternalFS journals preserve progress approximately every 4 KiB, after flash flush/readback; a torn journal causes rollback/retransmission. Energy snapshots use separate filenames. Staging does not imply permission to install.
- Before approval, the receiver requires the expected full SHA256, exact frame/length, format-2 signed FULL/codec-0 package, profile/target, size bound, trusted Ed25519 signature, Merkle leaves/root, image SHA256, sane application vectors and matching EndF/body hash. Unsigned, wrong-board, delta, bootloader and already-approved packages are refused.
- The `APRV` marker is written only immediately before a deliberate bootloader handoff, after verification and the reply-drain period. The bootloader performs its own installation checks. Stock/incompatible bootloaders cannot be bypassed. No bootloader migration, auto-apply, automatic rollback or anti-downgrade guarantee is added.
- Full images need thousands of request/reply exchanges, potentially hours or longer with hops, losses and airtime limits. This initial implementation does not provide delta updates, multicast distribution or bandwidth-efficient binary mOTA transport. Existing radio airtime restrictions remain active; do not raise airtime limits to hurry an update. `--pace` can increase pacing.
- Flash operations/verification can delay sensor polling. The existing power integrator records gaps in coverage instead of inventing energy during those gaps. It continues the normal application outside such operations.
- Staging uses roughly 9 KiB of heap only while an OTA session/status object is allocated, plus small verifier buffers. Static compiler RAM output does not measure peak runtime stack/heap. Exact memory bounds and application reservations are unchanged.
- Host transfer/package/crypto tests and ARM compilation are software checks. Real direct/multihop radio transfer, actual module recovery after interrupted writes, actual OTAFIX install and power-cut recovery have not been tested by Codex. Do the first physical installation with local recovery access. No remote flashing was performed while developing this feature.

## Commands

The **0.4.1-ota-test.1** test build adds a marker absent from the 0.4.0 receiver installed over Bluetooth DFU. After the mesh update, run **`ota test`** (alias **`pm ota test`**) in authenticated Repeater Admin. It replies `OTA update done - TEST1 | PM 0.4.1-ota-test.1 | git <source>`. The reply identifies the running test firmware; the same reply would appear if this test image were installed locally, so it is not independent evidence of the transfer method. `help`, `pm help` and `pm ota help` list the command. Running it does not touch flash, allocate a transfer session or activate an update.

| Command | Purpose |
|---|---|
| `pm ota status` | Pairing, bootloader, capacity, current/durable position and transfer ID |
| `ota test` / `pm ota test` | Read-only TEST1/version marker, added in 0.4.1 |
| `pm ota result` | Last activation status/abort reason in this boot |
| `pm ota begin <bytes> <SHA256>` | Start/resume one exact container (normally uploader-managed) |
| `pm ota data <id8> <offset> <hex>` | Upload at most 40 bytes (uploader-managed) |
| `pm ota verify <id8>` | Verify the complete container without approval/reset |
| `pm ota apply <id8>` | Reverify, then schedule explicit bootloader activation |
| `pm ota cancel` | Cancel pending apply and durably invalidate the staged container |
| `pm ota trust <pubkey>` | Provision/replace one trusted Ed25519 public key; local USB only |
| `pm ota pair RAK4631_RAK15001_C` | Confirm the exact physical bootloader/storage pairing; local USB only |

## Code provenance

The optional storage/container verification subset under `firmware/ota/` is vendored from [Mesh-America/mesh-america-quake-repeater](https://github.com/Mesh-America/mesh-america-quake-repeater/tree/c908bb09e68ca81e1d19198776e0f2e5b7e48653/src/helpers/ota), revision `c908bb09e68ca81e1d19198776e0f2e5b7e48653`, with its MIT license. One explicit `reopenPartial()` method was added to the flash driver for journal-backed sequential resume before the trailer has arrived. The portable container, Merkle and signature verifier are otherwise unchanged. Its custom mesh core, radio OTA engine, framework patches, auto-storage and bootloader updater are not imported. Mesh routing remains the pinned official base. One read-only Dispatcher accessor exposes an in-flight transmission so activation waits for it as well as the outbound queue; routing behavior is unchanged.
