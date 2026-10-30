#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <stdint.h>
#include "EnergyIntegrator.h"
#include "SolarHistory.h"
#include <CayenneLPP.h>
#ifndef PM_VERSION
#define PM_VERSION "0.4.0-dev"
#endif
#ifndef PM_SOURCE_SHA
#define PM_SOURCE_SHA "unknown"
#endif
#ifndef PM_SOLAR_SHUNT_OHMS
#define PM_SOLAR_SHUNT_OHMS 0.100f
#endif
#ifndef PM_LOAD_SHUNT_OHMS
#define PM_LOAD_SHUNT_OHMS 0.100f
#endif
#ifndef PM_SOLAR_SIGN
#define PM_SOLAR_SIGN 1
#endif
#ifndef PM_LOAD_SIGN
#define PM_LOAD_SIGN 1
#endif
#ifndef PM_SAMPLE_MS
#define PM_SAMPLE_MS 20UL
#endif
#ifndef PM_CHECKPOINT_MS
#define PM_CHECKPOINT_MS 900000UL
#endif
#ifndef PM_TEMPERATURE_MS
#define PM_TEMPERATURE_MS 60000UL
#endif

namespace pm {
class PowerMonitor {
public:
  void begin(bool allow_checkpoint);
  void poll(uint32_t milliseconds, uint32_t utc_seconds);
  void appendTelemetry(CayenneLPP&,uint8_t permissions) const;
  bool handleCommand(const char*, char*, size_t);
  bool checkpointNow() { return save(); }
private:
  struct Channel {
    uint8_t address = 0;
    float shunt_ohms = 0.1f;
    int8_t sign = 1;
    bool detected = false;
    bool valid = false;
    bool math_overflow = false;
    uint32_t failures = 0;
    float volts = NAN, milliamps = NAN, milliwatts = NAN;
    Integrator counter;
  };
  Channel solar_, load_;
  bool checkpoint_enabled_ = false, mcp_found_ = false, checkpoint_ok_ = false;
  bool mcp_ack_ = false;
  uint16_t mcp_manufacturer_=0, mcp_device_=0, mcp_raw_=0;
  SolarHistory history_;
  float mcp_temperature_ = NAN;
  uint32_t next_sample_ = 0, next_temperature_ = 0, next_checkpoint_ = 0, utc_ = 0;
  uint32_t next_probe_ = 0;
  uint32_t utc_day_ = 0, sequence_ = 0, restores_ = 0;
  double today_solar_ = 0, today_load_ = 0;
  static bool probe(uint8_t);
  static bool read16(uint8_t, uint8_t, uint16_t&);
  static bool write16(uint8_t, uint8_t, uint16_t);
  void sample(Channel&,uint32_t utc);
  void readMcp();
  void detectMcp();
  void summary(char*, size_t) const;
  bool save();
  bool restore();
  void clear();
};
}
