# PowerMonitor 0.4.2-bootstrap.2

Corrects the bootstrap.1 bootloader hash diagnostic and signed target-ID hash by using software SHA256 for constants/internal flash. MeshCore's CC310 helper ignores crypto errors; its hardware DMA must not be given a flash pointer. The exact bootloader hash/profile checks remain enforced.

Use the application UF2 on the USB bootloader drive, or application ZIP with a compatible Legacy DFU uploader. Leave the existing OTAFIX 2.4.12 / S140 6.1.1 bootloader installed. After reboot run `pm version` and `pm ota boot`. Expected version: `0.4.2-bootstrap.2`; expected boot hash prefix `ec860fb46697ac4b`, `handoff=52 match=1`. If the mismatch remains, report the output; do not bypass the gate.

Built on the Raspberry Pi from source commit 0b95e64. OTA host tests and actual ARM compilation passed. Package checks passed: SHA256/sizes, HEX/BIN equivalence, UF2 family/order/address bounds and embedded version/revision. BIN 380588 bytes. No hardware flash or physical bootloader-hash confirmation was performed by Codex. User confirmation remains required to establish that this fixes the observed mismatch.
