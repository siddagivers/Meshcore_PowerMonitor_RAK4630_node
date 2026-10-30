# PowerMonitor 0.4.1-ota-test.1 — TEST1 marker

This is a new OTA-compatible application for testing updates of the 0.4.0 receiver already installed over Bluetooth DFU. Hardware/bootloader pairing remains RAK4630/RAK4631 + RAK15001 slot C + matching OTAFIX, S140v6.1.1/B6. No bootloader or SoftDevice update.

Upload the ZIP (or BIN) and its matching JSON manifest through the Pi web uploader, then sign/transfer/activate using the existing OTA setup. The website now links both test files. A signer must first be created on the Pi and its public key/storage pairing provisioned once on the target; the firmware does not bypass those gates. No production signing key or signed production package was created automatically.

After reconnecting to the updated repeater, run:

```text
ota test
```

Expected reply:

```text
OTA update done - TEST1 | PM 0.4.1-ota-test.1 | git 36c607ea685e
```

Alias: `pm ota test`. Find it with `help`, `pm help`, or `pm ota help`. The marker is absent from the old 0.4.0 receiver. It is read-only and does not allocate OTA storage or trigger activation. It proves the test image is running; it does not independently identify whether the image arrived over LoRa or local DFU.

Compiled source: 36c607ea685eb8b90f79d46f26f8ba7bfaf54f98. Official MeshCore v1.18.0 base 81dbae592ffad40b4212bc0b37e82b38da08f4bc. BIN 380108 / 712704 application bytes; static RAM 41896 / 235520 bytes (runtime heap/stack additional). ZIP 380911 bytes; SHA256 52bd8f29aec0ff44cd4f34eab997b0080b2aed9ae089c8fe9bd240a8c9a42869.

Existing software tests and ARM build passed. Verified manifest hashes/sizes, HEX/BIN equivalence and bounds, UF2 family/order/bytes, application-only DFU ZIP/BIN/CRC16/B6, embedded TEST1/version/source, absence of marker in old image, and new-image signing/verification using an ephemeral test key and the actual C++ verifier. No repeater was flashed or sent radio commands by Codex; physical LoRa installation/command replies remain for the owner's test.
