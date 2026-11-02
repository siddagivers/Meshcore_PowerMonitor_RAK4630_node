# Companion inbox and shared serial connection

The Pi inbox runs at `https://192.168.1.16:8444/`, using the same admin login and TLS certificate as the OTA uploader on 8443. `meshcore-inbox.service` is a user service. It persists incoming private/channel messages, telemetry and acknowledgment events in `/home/pi/.local/share/meshcore-inbox/inbox.sqlite3`. The page displays the newest 200 events, unread counts, contacts, configured channels and discovered advertisements. Sends, telemetry requests and contact changes require explicit page actions. It does not periodically broadcast or request telemetry.

The service owns one serial connection to the confirmed RAK companion. An owner-only Unix socket accepts commands from the web page, collector bridge and OTA sender. Telemetry transactions and local serial command sends are serialized. OTA waits for a telemetry transaction before sending, with its remote reply timeout starting after the serial send. Waiting for an OTA response does not monopolize the companion and starve the existing collector. Incoming message fetching remains active. Private message sends show local acceptance; acknowledgment events are stored separately. Channel messages have no delivery acknowledgment.

## Existing collector audit

The live `pi` crontab runs `/home/pi/tools/dblogging/siprun_telemetry.sh` every five minutes under `/home/pi/automation-collectors/state/cron-siprun_telemetry_sh.lock`. The script also holds `/tmp/meshcore-siprun.lock`, uses `/dev/ttyACM0`, polls `SK-RK-SIPRUN`, writes `/home/pi/meshcore-siprun/data/latest.json` and `history.jsonl`, updates Domoticz indexes 8791–8800 and has existing failure alerts. Its original serial reader was `/home/pi/.local/bin/meshcli`. That lock did not coordinate with the original OTA sender.

The crontab, poll frequency, collector outputs, timeout/retry policy, Domoticz settings and alert logic are preserved. A backup is retained before replacing only the collector's `MESHCLI` assignment with the executable `scripts/companion_meshcli.py` bridge. It supports the collector's three existing commands: `req_telemetry`, `reset_path` and `path`. Before initial broker handover it falls back to the original meshcli; once the broker reports online it must not open another serial reader. Telemetry JSON retains `name`, `pubkey_pre` and `lpp`. The collector's existing flood fallback is preserved; the OTA sender itself does not initiate flood fallback.

The broker waits for existing serial readers and the collector lock before opening the companion. It never kills a process, resets the radio or interrupts an existing OTA transfer. A transfer already running with the old direct-serial sender remains outside the broker until it finishes. New uploads use the broker when its socket is available. Do not open meshcli or another independent serial reader against the same port once the broker is online.

## Operation and recovery

`systemctl --user status meshcore-inbox.service` and `journalctl --user -u meshcore-inbox.service` report service health. HTTP and socket handlers do not log passwords or request bodies. The signing private key is unrelated to this service and is not read by it. Channel secret keys are never returned to the browser. Existing radio configuration and channel definitions are not changed.

On serial failure the inbox reconnects; cached messages and contacts remain visible. Messages arriving while disconnected may be lost if the companion queue overflows; continuous receipt is not guaranteed through outages or old direct-serial OTA sessions. An interrupted OTA remains staged and can resume with the same signed package. A changed collector contact name or removed contact can break the existing poll, so contact removal requires confirmation.

Manual contacts can be added by full public key, name and type, or by exported `meshcore://` card. The page shows existing configured channels; it does not expose or edit their secret keys. No end-to-end radio delivery is claimed by host-only tests.
