#pragma once
#include <stdint.h>
#include <math.h>

namespace pm {
// A gap >200ms is unmeasured, never silently extrapolated as if a 700mA TX burst had not happened.
static const uint32_t MAX_GAP_MS = 200;
struct Integrator {
  bool have_last = false;
  uint32_t last_ms = 0;
  float last_mw = 0;
  double total_mwh = 0;
  double window_mwh = 0;
  uint64_t covered_ms = 0;
  uint64_t missed_ms = 0;
  uint32_t good_samples = 0;
  uint32_t bad_samples = 0;
  void add(uint32_t now_ms, float power_mw) {
    if (!isfinite(power_mw)) { bad_samples++; gap(now_ms); return; }
    if (have_last) {
      const uint32_t dt = now_ms - last_ms; // millis() overflow is safe
      if (dt && dt <= MAX_GAP_MS) {
        const double value = ((double)last_mw + (double)power_mw) * 0.5 * dt / 3600000.0;
        total_mwh += value;
        window_mwh += value;
        covered_ms += dt;
      } else if (dt > MAX_GAP_MS) missed_ms += dt;
    }
    last_ms = now_ms;
    last_mw = power_mw;
    have_last = true;
    good_samples++;
  }
  void gap(uint32_t now_ms) {
    if (have_last) missed_ms += (uint32_t)(now_ms - last_ms);
    have_last = false;
  }
  void resetWindow() {
    window_mwh = 0; covered_ms = 0; missed_ms = 0;
    good_samples = 0; bad_samples = 0;
  }
  unsigned coverage() const {
    const uint64_t n = covered_ms + missed_ms;
    return n ? (unsigned)(100ULL * covered_ms / n) : 0U;
  }
};
} // namespace pm
