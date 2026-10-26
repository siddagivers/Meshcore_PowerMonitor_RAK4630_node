#include "../firmware/EnergyIntegrator.h"
#include <cassert>
#include <cmath>
#include <cstdio>
static bool near(double a,double b,double tol=1e-7){return fabs(a-b)<tol;}
int main(){
  pm::Integrator x;
  x.add(0,1000);x.add(20,1000);
  assert(near(x.total_mwh,1000*20.0/3600000));
  for(unsigned n=40;n<=1000;n+=20) x.add(n,1000);
  assert(near(x.total_mwh,1000*1000.0/3600000));
  x.add(1020,2800);x.add(1040,2800);
  assert(near(x.total_mwh,(1000*1000.0+1900*20+2800*20)/3600000));
  const double before=x.total_mwh;
  x.add(2000,1000);
  assert(near(x.total_mwh,before));
  assert(x.missed_ms==960);
  x.add(2020,-200);
  assert(x.total_mwh>0);
  pm::Integrator wrap;
  wrap.add(0xFFFFFFF0u,1000);wrap.add(16u,1000);
  assert(wrap.covered_ms==32);
  printf("PASS: constant load, simulated TX burst, gaps, negative readings, millis wrap\n");
}
