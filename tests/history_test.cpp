#include "SolarHistory.h"
#include "PowerTelemetry.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <vector>
struct Field { unsigned channel;const char* type;double value; };
struct Encoder {
  std::vector<Field> fields;
  void addPercentage(unsigned c,unsigned v){fields.push_back({c,"coverage",double(v)});}
  void addGenericSensor(unsigned c,float v){fields.push_back({c,"mWh",v});}
  void addEnergy(unsigned c,float v){fields.push_back({c,"kWh",v});}
  void addAnalogInput(unsigned c,float v){fields.push_back({c,"W",v});}
};
int main() {
  constexpr uint32_t day=20000UL,midnight=day*86400UL;
  pm::SolarHistory history;
  // Two hours at 1 W, accumulated at 100-ms intervals like a fast sampler.
  const uint32_t start=midnight+3600;
  for(uint32_t tick=0;tick<72000;tick++)
    history.add(start+tick/10,1000.0*100.0/3600000.0,100);
  auto quarter=history.rolling(start+7200,900);
  auto hour=history.rolling(start+7200,3600);
  assert(std::fabs(quarter.mwh-250)<0.01 && quarter.coverage()==100);
  assert(std::fabs(hour.mwh-1000)<0.1 && hour.coverage()==100);
  assert(std::fabs(hour.watts()-1)<0.0001);
  assert(std::fabs(history.today(start+7200).mwh-2000)<0.01);
  // A boundary inside a bucket excludes <10 s, and reports the missing coverage.
  auto partial=history.rolling(start+7203,900);
  assert(partial.covered_ms==890000 && partial.coverage()==98);
  // Missing samples do not become fabricated energy after restore or a gap.
  pm::SolarHistory restored;
  std::memcpy(&restored.state,&history.state,sizeof(history.state));
  auto gap=restored.rolling(start+7500,900);
  assert(gap.coverage()==66 && std::fabs(gap.mwh-1000.0/6)<0.1);
  assert(restored.rolling(start+10801,3600).covered_ms==0);
  // Midnight freezes the completed UTC day; an entirely skipped day is unavailable.
  restored.advance(midnight+86400);
  assert(std::fabs(restored.previous(midnight+86400).mwh-2000)<0.01);
  assert(restored.previous(midnight+86400).coverage()==8);
  assert(restored.today(midnight+86400).covered_ms==0);
  restored.add(midnight+86401,2,100);
  assert(restored.today(midnight+86402).mwh==2);
  restored.advance(midnight+3*86400);
  assert(restored.previous(midnight+3*86400).covered_ms==0);
  // No wall-clock history before time synchronization; backward jumps clear buckets.
  pm::SolarHistory unsynced;unsynced.add(0,1,100);
  assert(unsynced.state.day==0);
  history.advance(start);
  assert(history.rolling(start,3600).covered_ms==0);
  // Native energy uses kWh; the companion generic field is mWh, analog field W.
  Encoder lpp;pm::appendSolarReading(lpp,110,quarter);
  assert(lpp.fields.size()==4);
  assert(lpp.fields[0].value==100);
  assert(std::fabs(lpp.fields[1].value-250)<0.01);
  assert(std::fabs(lpp.fields[2].value-0.00025)<1e-8);
  assert(std::fabs(lpp.fields[3].value-1)<0.0001);
  // Unsigned LPP fields never wrap negative energy; signed average remains usable.
  Encoder negative;
  pm::appendSolarReading(negative,111,pm::SolarHistory::Reading{-10,36000,36000});
  assert(negative.fields.size()==2 && negative.fields[1].value==-1);
  Encoder empty;pm::appendSolarReading(empty,112,pm::SolarHistory::Reading{});
  assert(empty.fields.size()==1 && empty.fields[0].value==0);
  history.clear();
  assert(history.state.day==0 && history.state.today_mwh==0);
  for(const auto& bucket:history.state.buckets)
    assert(bucket.utc==0 && bucket.mwh==0 && bucket.covered_ms==0);
  puts("PASS: rolling solar windows, gaps, persistence state, UTC days, clock rollback and telemetry units/signs");
}
