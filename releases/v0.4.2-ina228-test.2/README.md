# INA228 test.2

Source 068baa248538. Battery **0x40**, solar **0x41**, both R100 shunts.
This reverses test.1's addresses, as requested. Battery A1/A0=GND/GND;
solar A1/A0=GND/VS (3.3-V logic supply). Jumper topology must be checked
before removing ground bridges or adding VS connections.

Adds persistent `pm ina off` / `pm ina on`, described `pm help 1` through
`pm help 12`, and separate `radio off 40`, `radio on`, `radio status`,
`radio help`. Radio pause waits >=10 seconds and for queue/TX drain; cancels
if still busy at 60 seconds. Pause duration starts at actual radio sleep.
USB/sensors keep running; early resume requires USB while RF is paused.
No pause is persisted across reboot. INA disable preserves all historical data
and the battery continuous/five-minute choice. It requests ADC shutdown,
does not disconnect supply power, and reports shutdown/persistence errors.

See [command descriptions](../../docs/PM_COMMANDS.md) and
[INA228 profile details](../../docs/INA228_TEST.md).

BIN394208 bytes. Real ARM build, DFU CRC/S140 B6, HEX/BIN/UF2 addresses,
family/order/byte equivalence and manifest hashes passed. Full-size signed
package prepared with a disposable key and accepted by the software verifier;
untrusted/tampered variants rejected. Native tests cover persistence failures,
all help page lengths, timed radio state transitions/queue guarding/wraparound,
INA228 arithmetic/history, and existing firmware regressions.

Hardware RF sleep/resume, INA shutdown and long-duration operation are not
claimed as tested. Install UF2 locally or use a compatible app DFU uploader
with the ZIP. No bootloader replacement, automatic flash or radio setting
change is included. Keep the recovered identity backup.
