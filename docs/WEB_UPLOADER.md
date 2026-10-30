# Raspberry Pi firmware web uploader

The installed page is **https://192.168.1.16:8443** on `pi5-grob`. It uses its own HTTPS listener; existing Pi websites, automation, Zigbee and other serial services are untouched. The TLS certificate is generated locally for this Pi, so a browser may ask the user to accept it on the first visit. Username is `admin`; the generated password was supplied to the owner separately and is not stored in this repository. Only a salted password hash is stored on the Pi.

The page includes a download of the initial receiver phone DFU ZIP and its matching JSON manifest. Installing the receiver and provisioning its signer/storage pairing are still required before testing mesh updates; see [LoRa OTA setup](LORA_OTA.md).

## Using the page

1. Sign in, then choose **Create signing key on Pi** once. It shows only the public key and the exact local USB provisioning commands. The private signing key stays at `/home/pi/.local/share/power-monitor-web/signing.pem`, mode 600. Back up that private key securely. The page will not overwrite an existing key.
2. Select a new **RAK15001 LoRa OTA** BIN or application-only phone DFU ZIP plus its matching build JSON. Choose **Verify and sign firmware**. File names may change during download, but the complete file hash/size and decompressed application hash must match the manifest. A default no-OTA build is rejected. Alternatively import an already signed `.mota` package.
3. Select the **confirmed companion** USB serial port, enter the exact target public key and repeater admin password. Listed RAK/ACM ports are not automatically probed or assumed to be companions. Zigbee/other USB serial devices are not offered by default. A different intentional companion path can be explicitly whitelisted with the service environment variable `PM_OTA_PORTS`.
4. Choose **Upload over mesh and verify** to stage only. **Upload, verify and activate** is a separate explicit choice and confirmation. Preparing/uploading a file to the website never starts the radio transfer by itself.
5. Follow acknowledged-byte progress and logs. Stopping the sender cannot reverse an activation already accepted remotely. Check `pm version` after an installation. The receiver retains its previous pairing/bootloader checks and never auto-installs a staged image.

The repeater admin password is passed to the sender over a private stdin pipe, never command-line arguments, files or saved job metadata. Output is redacted before the web log is retained. The page keeps one transfer at a time and requires login and same-origin request protection for upload/start/key operations. TLS protects the web credentials in transit.

Packages persist under `/home/pi/.local/share/power-monitor-web/packages/`, limited to 20 distinct packages. No production firmware-signing key is created merely by installing or visiting the page; the owner creates it explicitly in the UI. Job status/logs are held in memory. Restarting the web service stops an active sender; rerun the same package to resume from the target checkpoint.

## Service and build environment

```sh
cd /home/pi/Meshcore_PowerMonitor_RAK4630_node
. .venv/bin/activate
python -m pip install -r requirements-build.txt -r requirements-ota.txt
bash tests/run_tests.sh
bash tests/run_ota_tests.sh
```

The Pi's `.venv` contains PlatformIO 6.2.0, IntelHex 2.3.0, the pinned ARM platform/framework/toolchain cache, the MeshCore 2.3.17 uploader and cryptography. A complete `official-lora-ota` environment-check build passed without flashing. The separate `.ota-tools-venv` remains available as well.

Installed persistent user service:

```sh
systemctl --user status power-monitor-web.service
systemctl --user restart power-monitor-web.service
journalctl --user -u power-monitor-web.service --no-pager -n 30
```

Its template is [deploy/power-monitor-web.service](../deploy/power-monitor-web.service). User lingering is enabled so the service starts without an interactive Pi login. Configuration is `/home/pi/.config/power-monitor-web/`: `auth.json`, `cert.pem`, `tls-key.pem`. Authentication hash and private TLS/signing files are private to `pi`; none is committed. The app runs as `pi`, not root. Port 8443 was unused before deployment; no router/Internet port forwarding was added.

Tests cover missing login, cross-site-write rejection, key overwrite protection, malformed packages, real DFU ZIP/hash/CRC preparation, renamed downloads, no automatic radio access, target/port validation, password exclusion/redaction, and stage-only operation. Live LAN checks verified TLS using the certificate obtained through SSH, authenticated page/assets/status, and the exact receiver ZIP download hash. Actual radio installation still requires the owner's hardware test; installing this page did not send firmware or open a companion port.
