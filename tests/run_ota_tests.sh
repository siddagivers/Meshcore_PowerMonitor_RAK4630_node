#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tests/ota_package_test.py /tmp/pm-ota-test.mota
g++ -std=c++17 -Wall -Wextra -Werror -I tests/ota_mocks -I firmware \
 tests/ota_verify_test.cpp firmware/ota/OtaVerify.cpp firmware/ota/MotaContainer.cpp \
 firmware/ota/MerkleTree.cpp -lcrypto -o /tmp/pm-ota-verify-test
/tmp/pm-ota-verify-test /tmp/pm-ota-test.mota
python3 -m py_compile scripts/lora_ota.py scripts/inject.py
python3 tests/ota_radio_test.py
