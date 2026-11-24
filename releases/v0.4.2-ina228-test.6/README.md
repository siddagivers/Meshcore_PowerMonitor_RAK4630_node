# RAK4631 INA228 test.6 USB baseline

Copy the application UF2 to the RAK4631 USB bootloader drive. After the
repeater restarts, `pm version` should report `0.4.2-ina228-test.6`.

This build contains the two INA228 channels, MCP9808, environmental telemetry,
completed UTC-day history and RAK15001 MeshCore OTA support. The sensor task
is reused and releases the telemetry buffer after each request. See the
[sensor and telemetry guide](../../docs/INA228_TEST.md).

Before the mesh test, check `pm ota boot` and `pm ota status`. The repeater
needs a compatible OTAFIX bootloader, provisioned pairing and trusted signer,
and a working RAK15001 in slot C. Use the matching ZIP and JSON from
[test.7](../v0.4.2-ina228-test.7/) in the Pi uploader. Both versions were built
from source commit `a5a1c7973cbe`.
