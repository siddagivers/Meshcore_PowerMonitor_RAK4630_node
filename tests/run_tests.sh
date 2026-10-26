#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
g++ -std=c++17 -Wall -Wextra -Werror -I firmware tests/integrator_test.cpp -o /tmp/pm_integrator_test
/tmp/pm_integrator_test
g++ -std=c++11 -Wall -Wextra -Werror -I firmware tests/history_test.cpp -o /tmp/pm_history_test
/tmp/pm_history_test
python3 -m py_compile scripts/inject.py
echo "PASS Python injection script syntax"
