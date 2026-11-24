#include <cassert>
#include <cstdio>
int main(){
 constexpr unsigned payload=184,mac=2,block=16,tag=4;
 constexpr unsigned budget=payload-mac-(block-1)-tag;
 static_assert(budget==163,"Pinned MeshCore budget changed");
 auto accepted=[](unsigned data){return data+mac+block-1<=payload;};
 assert(!accepted(180+tag));assert(!accepted(179+tag));
 assert(accepted(budget+tag));assert(!accepted(budget+tag+1));
 assert(2+mac+((budget+tag+block-1)/block)*block<=payload);
 // All INA228 V/I/P windows, coverage, ages and base voltage fit.
 assert(10*12+8*3+2*6+4<=budget);
 // Combined page still fits at full INA history, with room for board V/T,
 // MCP9808 and the environmental record (temperature, humidity, pressure).
 assert(10*12+4+4+4+4+3+4<=budget);
 puts("PASS encrypted telemetry limits, worst-case AES padding, maximum-size boundary, and all INA228 groups");
}
