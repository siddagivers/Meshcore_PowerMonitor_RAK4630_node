# PowerMonitor 0.4.2-bootstrap.4

Source: e0ed10d61a77. Official MeshCore v1.18.0, pinned upstream
81dbae592ffad40b4212bc0b37e82b38da08f4bc.

Recovery receiver for the verification freeze reported on bootstrap.3. OTA
verification uses a separate 16 KiB task stack and software SHA256/Ed25519,
avoiding the deep 4 KiB command task stack and unbounded CC310 hardware wait.
A 30-second command wait returns progress if the worker has not completed;
staging mutations remain locked until its result is collected. `pm ota result`
reports verification state and completed worker minimum unused stack bytes.
The exact instruction responsible for the physical freeze is not proven.

Install this **application UF2** on the existing bootloader USB drive.
No bootloader replacement is required. Source, pairing, signer and staged
transfer journal formats remain compatible; do not issue `pm ota cancel`.

After restart:

```text
pm version
pm ota status
pm ota verify a6343a3d
pm ota result
```

The displayed image ID applies only to the previously reported complete
test.3 stage. Do not activate that old image: it restores the old verifier.
Use ota-test.4 for a new activation test.

BIN: 389000 bytes, static RAM: 42272 / 235520 bytes. Verification stack is a
temporary heap allocation. Full package SHA256 values are in the JSON and
sha256 files. Actual ARM compilation, Nordic DFU CRC16/S140 B6, HEX/BIN and
UF2 byte/range/family equivalence passed. Signed full-size packages passed
the software verifier; damaged signatures/data and untrusted signers failed.
No physical device was flashed or verified by Codex. Hardware retest required.
