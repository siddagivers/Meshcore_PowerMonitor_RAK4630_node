#include "BoundedWireWait.h"
#include <cassert>
#include <cstdio>
int main() {
  unsigned calls=0;uint32_t tick=0;
  assert(pm::boundedWireWait([&](){return ++calls==3;},[&](){return tick++;},50,100));
  tick=0;calls=0;
  assert(!pm::boundedWireWait([&](){++calls;return false;},[&](){return tick++;},50,1000));
  assert(calls<=51);
  calls=0;
  assert(!pm::boundedWireWait([&](){++calls;return false;},[](){return 7u;},50,10));
  assert(calls==11);
  tick=0xfffffff0u;calls=0;
  assert(!pm::boundedWireWait([&](){++calls;return false;},[&](){return tick++;},50,1000));
  assert(calls<=51);
  puts("PASS: ready events, timeout, frozen clock spin bound and clock rollover");
}
