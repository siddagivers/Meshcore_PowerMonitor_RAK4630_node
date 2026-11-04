# Receiver verification recovery: bootstrap.4 / ota-test.4

Reported on bootstrap.3: a complete 382738-byte package survived reboot, but
`pm ota verify a6343a3d` produced no response and both USB and LoRa became
unresponsive. No successful activation was established.

The deployed Arduino core gives the loop task 4096 bytes of stack. ARM
disassembly showed 1304 bytes in the outer verifier, another 624 bytes in
the streaming verifier, and 384 bytes in its command handler, before the
receive path and crypto/library call frames. The OTA Merkle and Ed25519
paths also called MeshCore's CC310 helpers; the vendor hardware interrupt
wait has no timeout. These are concrete risks, not proof of which instruction
froze the reported device.

The corrected receiver isolates verification on a FreeRTOS task with a
16384-byte stack allocated only while verifying. The worker uses software
SHA256 and Ed25519, never MeshCore's shared CC310 workspace. The original
signer, profile, Merkle, image hash, vectors, EndF and bootloader checks remain.
Only the loop task accesses InternalFS and changes the verified flag.

The command waits at most 30 seconds for the worker. If it is still active,
it returns a progress diagnostic, locks provisioning/staging/activation
changes, and allows `pm ota status`, `pm ota boot`, `pm ota test`, and
`pm ota result`. Repeat `pm ota verify <id>` to collect the worker's result.
The result includes the completed worker's minimum unused stack in bytes.
There is no automatic reboot or activation.

Install bootstrap.4 locally through UF2 first, without changing the bootloader
or cancelling the staged package. Existing pairing, signer and resume journals
use the same files and format. Use `pm ota result` to report verification
diagnostics. A previous test.3 package can be used to check verification, but
do not activate it: it reinstalls the old verifier. Use the matching
ota-test.4 ZIP and JSON to prepare the next update instead.

Validation includes actual ARM builds and package layout checks; native tests
with real signed and corrupted containers; and a test linked against the same
software Crypto library as the receiver. This does not establish success on
physical QSPI/RAK hardware. The reported freeze must be retested on the device.
