#pragma once
#include <stdint.h>
namespace pm {
// Clock wrap and a stalled clock are both bounded. The independent spin cap
// avoids relying on interrupts to advance the deadline during a driver fault.
template<class Ready,class Clock>
bool boundedWireWait(Ready ready,Clock clock,uint32_t timeout_us,uint32_t max_spins) {
  const uint32_t start=clock();
  while(!ready()) {
    if(!max_spins-- || (uint32_t)(clock()-start)>=timeout_us)return false;
  }
  return true;
}
}
