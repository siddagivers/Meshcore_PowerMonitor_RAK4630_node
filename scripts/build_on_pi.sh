#!/usr/bin/env bash
# Versioned Raspberry Pi/Debian/GitHub Actions build. Never auto-flashes hardware.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REV="81dbae592ffad40b4212bc0b37e82b38da08f4bc"
URL="https://github.com/meshcore-dev/MeshCore.git"
PROFILE="${1:-official}"
if [[ "$PROFILE" != official ]];then echo "Only the official no-LoRa-OTA profile is supported" >&2;exit 2;fi
command -v git >/dev/null || { echo "git required" >&2;exit 2; }
command -v pio >/dev/null || { echo "Install PlatformIO in a Python venv: pip install platformio" >&2;exit 2; }
python3 -c 'import intelhex' || { echo "Install build dependencies in the active venv: pip install -r requirements-build.txt" >&2;exit 2; }
BASE="$(tr -d '\r\n' < "$ROOT/VERSION")"
SUFFIX="${PM_BUILD_SUFFIX:-local.$(date -u +%Y%m%d%H%M%S)}"
FULL="$BASE-$SUFFIX"
SHA="${PM_SOURCE_SHA:-$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)}"
UP="$ROOT/upstream-official"
if [[ ! -d "$UP/.git" ]];then git clone "$URL" "$UP";fi
git -C "$UP" fetch origin "$REV"
git -C "$UP" checkout --detach "$REV"
git -C "$UP" restore examples/simple_repeater/main.cpp examples/simple_repeater/MyMesh.cpp variants/rak4631/platformio.ini
python3 "$ROOT/scripts/inject.py" "$UP" --version "$FULL" --source-sha "$SHA"
(cd "$UP" && pio run -e RAK_4631_repeater_power_monitor)
# Official upstream has no custom EndF/LoRa-OTA post-action. A BIN
# starts at the application base; UF2 retains the HEX destination addresses.
BUILD="$UP/.pio/build/RAK_4631_repeater_power_monitor"
python3 - "$BUILD" <<'PY'
from pathlib import Path
from intelhex import IntelHex
import sys
build=Path(sys.argv[1])
image=IntelHex(str(build/"firmware.hex"))
if image.minaddr()!=0x26000 or image.maxaddr()>=0xD4000:
 raise SystemExit("Unexpected application HEX range; refusing to package")
image.tobinfile(str(build/"firmware.bin"))
PY
python3 "$UP/bin/uf2conv/uf2conv.py" -f 0xADA52840 -c "$BUILD/firmware.hex" -o "$BUILD/firmware.uf2"
# Keep PlatformIO's real Nordic/Adafruit application DFU package, not a ZIP
# of arbitrary HEX/UF2 files. Check the package against the final application.
python3 - "$BUILD" <<'PY'
from pathlib import Path
import sys,zipfile,json,struct
b=Path(sys.argv[1])
with zipfile.ZipFile(b/"firmware.zip") as z:
 m=json.loads(z.read("manifest.json"))["manifest"]
 if set(m)!={"application","dfu_version"} or m["dfu_version"]!=0.5:
  raise SystemExit("Expected application-only Nordic/Adafruit DFU 0.5 package")
 app=m["application"];data=z.read(app["bin_file"]);init=z.read(app["dat_file"])
 if data!=(b/"firmware.bin").read_bytes():raise SystemExit("DFU binary does not match final HEX/BIN")
 crc=0xFFFF
 for byte in data:
  crc^=byte<<8
  for _ in range(8):crc=((crc<<1)^0x1021)&0xFFFF if crc&0x8000 else (crc<<1)&0xFFFF
 if len(init)!=14 or struct.unpack("<7H",init)[4:6]!=(1,0x00B6):
  raise SystemExit("DFU init packet must require S140 v6.1.1 (0x00B6)")
 if struct.unpack("<H",init[-2:])[0]!=crc or app["init_packet_data"]["firmware_crc16"]!=crc:
  raise SystemExit("DFU CRC16 validation failed")
 print("PASS: application-only DFU ZIP, matching BIN, CRC16, S140 0x00B6")
PY
OUT="$ROOT/output"
mkdir -p "$OUT"
PREFIX="RAK4631_official_no_lora_ota_PM_v${FULL}"
FOUND=0
FILES=()
for extension in uf2 hex bin zip;do
  src="$UP/.pio/build/RAK_4631_repeater_power_monitor/firmware.$extension"
  if [[ -f "$src" ]];then
    cp "$src" "$OUT/${PREFIX}.$extension"
    FILES+=("${PREFIX}.$extension")
    FOUND=$((FOUND+1))
  fi
done
if ((FOUND==0));then echo "No firmware output" >&2;exit 1;fi
(cd "$OUT" && sha256sum "${FILES[@]}" > "${PREFIX}.sha256")
export PM_SOURCE_SHA="$SHA" PM_FULL_VERSION="$FULL" PM_BUILD_ROOT="$ROOT"
python3 - <<'PY'
from pathlib import Path
import os,json,hashlib,datetime
o=Path(os.environ["PM_BUILD_ROOT"])/"output"
prefix="RAK4631_official_no_lora_ota_PM_v"+os.environ["PM_FULL_VERSION"]
items={}
for f in o.glob(prefix+".*"):
 if f.suffix in (".hex",".uf2",".bin",".zip"):
  items[f.name]={"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
metadata={
 "version":os.environ["PM_FULL_VERSION"], "source_commit":os.environ["PM_SOURCE_SHA"],
 "upstream":"81dbae592ffad40b4212bc0b37e82b38da08f4bc",
 "upstream_url":"https://github.com/meshcore-dev/MeshCore",
 "upstream_version":"v1.18.0",
 "target":"RAK_4631_repeater_power_monitor",
 "profile":"official_no_lora_ota", "lora_ota":False,
 "application_start":"0x26000", "application_limit":"0xD4000",
 "dfu":{"format":"Nordic/Adafruit legacy DFU 0.5","application_only":True,"softdevice_req":"0x00B6"},
 "built_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "firmware":items
}
(o/(prefix+".json")).write_text(json.dumps(metadata,indent=2)+"\n")
print(json.dumps(metadata,indent=2))
PY
echo "Compiled version $FULL. Artifacts: $OUT"
