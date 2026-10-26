#pragma once
#include <stdint.h>
#include <math.h>

namespace pm {
// Ten-second buckets preserve the 20-ms energy integral. Query boundaries
// omit the partially overlapping oldest bucket rather than inventing samples.
class SolarHistory {
public:
  static constexpr uint32_t BUCKET_SECONDS=10, BUCKET_COUNT=361;
  struct Bucket {
    uint32_t utc; float mwh; uint32_t covered_ms;
    Bucket(uint32_t time=0,float energy=0,uint32_t covered=0)
      :utc(time),mwh(energy),covered_ms(covered){}
  };
  struct State {
    uint32_t day=0, previous_day=0, last_utc=0;
    double today_mwh=0, previous_mwh=0;
    uint32_t today_ms=0, previous_ms=0;
    Bucket buckets[BUCKET_COUNT]{};
  } state;
  void clear() {
    // Reset in place: a State{} assignment can create a >4-KiB temporary
    // on the official Arduino loop task's small stack.
    state.day=state.previous_day=state.last_utc=0;
    state.today_mwh=state.previous_mwh=0;
    state.today_ms=state.previous_ms=0;
    for(auto& bucket:state.buckets)bucket=Bucket{};
  }
  struct Reading {
    double mwh;
    uint32_t covered_ms, span_ms;
    Reading(double energy=0,uint32_t covered=0,uint32_t span=0)
      :mwh(energy),covered_ms(covered),span_ms(span){}
    unsigned coverage() const {
      return span_ms ? (unsigned)fmin(100.0,100.0*covered_ms/span_ms) : 0;
    }
    double watts() const { return covered_ms ? mwh*3600.0/covered_ms : NAN; }
  };
  void advance(uint32_t utc) {
    if(utc<1700000000UL)return;
    const uint32_t day=utc/86400UL;
    if(state.last_utc && utc<state.last_utc) {
      // Clock rollback invalidates the wall-clock assignment of live buckets.
      for(auto& bucket:state.buckets)bucket=Bucket{};
    }
    if(state.day!=day) {
      if(state.day && day==state.day+1) {
        state.previous_day=state.day;state.previous_mwh=state.today_mwh;
        state.previous_ms=state.today_ms;
      } else {
        state.previous_day=0;state.previous_mwh=0;state.previous_ms=0;
      }
      state.day=day;state.today_mwh=0;state.today_ms=0;
    }
    state.last_utc=utc;
  }
  void add(uint32_t utc,double mwh,uint32_t covered_ms) {
    if(utc<1700000000UL||!isfinite(mwh)||!covered_ms)return;
    advance(utc);
    const uint32_t start=utc-utc%BUCKET_SECONDS;
    auto& bucket=state.buckets[(start/BUCKET_SECONDS)%BUCKET_COUNT];
    if(bucket.utc!=start)bucket=Bucket{start,0,0};
    bucket.mwh+=(float)mwh;bucket.covered_ms+=covered_ms;
    state.today_mwh+=mwh;state.today_ms+=covered_ms;
  }
  Reading rolling(uint32_t utc,uint32_t seconds) const {
    Reading out{};out.span_ms=seconds*1000UL;
    if(utc<1700000000UL)return out;
    for(const auto& bucket:state.buckets) {
      if(bucket.utc && bucket.utc<=utc && utc-bucket.utc<=seconds) {
        out.mwh+=bucket.mwh;out.covered_ms+=bucket.covered_ms;
      }
    }
    return out;
  }
  Reading today(uint32_t utc) const {
    if(utc<1700000000UL||state.day!=utc/86400UL)return Reading{};
    return Reading{state.today_mwh,state.today_ms,(uint32_t)((utc%86400UL)*1000UL)};
  }
  Reading previous(uint32_t utc) const {
    if(utc<1700000000UL||state.previous_day+1!=utc/86400UL)return Reading{};
    return Reading{state.previous_mwh,state.previous_ms,86400000UL};
  }
};
}
