#!/usr/bin/env bash
# Run after a real PlatformIO build has installed the pinned Crypto library.
set -euo pipefail
cd "$(dirname "$0")/.."
crypto=upstream-official/.pio/libdeps/RAK_4631_repeater_power_monitor/Crypto
test -f "$crypto/Ed25519.cpp"
python3 tests/ota_package_test.py /tmp/pm-ota-software-test.mota
g++ -std=c++17 -O2 -ffunction-sections -fdata-sections \
 -DPM_OTA_SOFTWARE_SIGNATURE=1 -I "$crypto" -I tests/ota_mocks -I firmware \
 tests/ota_verify_test.cpp firmware/ota/OtaVerify.cpp \
 firmware/ota/MotaContainer.cpp firmware/ota/MerkleTree.cpp \
 "$crypto/Ed25519.cpp" "$crypto/Curve25519.cpp" "$crypto/SHA512.cpp" \
 "$crypto/SHA256.cpp" "$crypto/Hash.cpp" "$crypto/Crypto.cpp" \
 "$crypto/BigNumberUtil.cpp" -Wl,--gc-sections -lcrypto -o /tmp/pm-ota-software-verify-test
/tmp/pm-ota-software-verify-test /tmp/pm-ota-software-test.mota
