#!/usr/bin/env bash
# Versioned Raspberry Pi/Debian/GitHub Actions build. Never auto-flashes hardware.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REV="c908bb09e68ca81e1d19198776e0f2e5b7e48653"
URL="https://github.com/Mesh-America/mesh-america-quake-repeater.git"
STORAGE="${1:-rak15001}"
case "$STORAGE" in rak15001|w25q16|unified) ;; *) echo "storage must be rak15001|w25q16|unified" >&2;exit 2;; esac
command -v git >/dev/null || { echo "git required" >&2;exit 2; }
command -v pio >/dev/null || { echo "Install PlatformIO in a Python venv: pip install platformio" >&2;exit 2; }
python3 -c 'import intelhex' || { echo "Install build dependencies in the active venv: pip install -r requirements-build.txt" >&2;exit 2; }
BASE="$(tr -d '\r\n' < "$ROOT/VERSION")"
SUFFIX="${PM_BUILD_SUFFIX:-local.$(date -u +%Y%m%d%H%M%S)}"
FULL="$BASE-$SUFFIX"
SHA="${PM_SOURCE_SHA:-$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || echo unknown)}"
UP="$ROOT/upstream"
if [[ ! -d "$UP/.git" ]];then git clone "$URL" "$UP";fi
git -C "$UP" fetch origin "$REV"
git -C "$UP" checkout --detach "$REV"
git -C "$UP" restore examples/simple_repeater/main.cpp examples/simple_repeater/MyMesh.cpp variants/rak4631/platformio.ini
python3 "$ROOT/scripts/inject.py" "$UP" --storage "$STORAGE" --version "$FULL" --source-sha "$SHA"
(cd "$UP" && pio run -e RAK_4631_repeater_power_monitor)
# Convert the final HEX, after upstream's EndF/layout post-action. A BIN
# starts at the application base; UF2 retains the HEX destination addresses.
BUILD="$UP/.pio/build/RAK_4631_repeater_power_monitor"
python3 - "$BUILD" <<'PY'
from pathlib import Path
from intelhex import IntelHex
import sys
build=Path(sys.argv[1])
image=IntelHex(str(build/"firmware.hex"))
if image.minaddr()!=0x26000 or image.maxaddr()>=0xED000:
 raise SystemExit("Unexpected application HEX range; refusing to package")
image.tobinfile(str(build/"firmware.bin"))
PY
python3 "$UP/bin/uf2conv/uf2conv.py" -f 0xADA52840 -c "$BUILD/firmware.hex" -o "$BUILD/firmware.uf2"
OUT="$ROOT/output"
mkdir -p "$OUT"
PREFIX="RAK4631_${STORAGE}_PM_v${FULL}"
FOUND=0
FILES=()
for extension in uf2 hex bin;do
  src="$UP/.pio/build/RAK_4631_repeater_power_monitor/firmware.$extension"
  if [[ -f "$src" ]];then
    cp "$src" "$OUT/${PREFIX}.$extension"
    FILES+=("${PREFIX}.$extension")
    FOUND=$((FOUND+1))
  fi
done
if ((FOUND==0));then echo "No firmware output" >&2;exit 1;fi
(cd "$OUT" && sha256sum "${FILES[@]}" > "${PREFIX}.sha256")
export PM_SOURCE_SHA="$SHA" PM_FULL_VERSION="$FULL" PM_STORAGE="$STORAGE" PM_BUILD_ROOT="$ROOT"
python3 - <<'PY'
from pathlib import Path
import os,json,hashlib,datetime
o=Path(os.environ["PM_BUILD_ROOT"])/"output"
prefix="RAK4631_"+os.environ["PM_STORAGE"]+"_PM_v"+os.environ["PM_FULL_VERSION"]
items={}
for f in o.glob(prefix+".*"):
 if f.suffix in (".hex",".uf2",".bin"):
  items[f.name]={"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()}
metadata={
 "version":os.environ["PM_FULL_VERSION"], "source_commit":os.environ["PM_SOURCE_SHA"],
 "upstream":"c908bb09e68ca81e1d19198776e0f2e5b7e48653",
 "target":"RAK_4631_repeater_power_monitor",
 "storage":os.environ["PM_STORAGE"],
 "built_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "firmware":items
}
(o/(prefix+".json")).write_text(json.dumps(metadata,indent=2)+"\n")
print(json.dumps(metadata,indent=2))
PY
echo "Compiled version $FULL. Artifacts: $OUT"
