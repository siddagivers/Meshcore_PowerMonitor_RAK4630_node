#include "InaEnable.h"
#include <cassert>
#include <cstdio>
int main(){
 assert(pm::loadInaEnabled(false));assert(pm::loadInaEnabled(true));
 assert(!pm::saveInaEnabled(false,false));assert(!InternalFS.present);
 assert(pm::saveInaEnabled(true,false));assert(!pm::loadInaEnabled(true));assert(InternalFS.data.size()==1);
 assert(pm::saveInaEnabled(true,true));assert(pm::loadInaEnabled(true));assert(InternalFS.data.size()==1);
 InternalFS.failRemove=true;assert(!pm::saveInaEnabled(true,false));assert(pm::loadInaEnabled(true));
 InternalFS.failRemove=false;InternalFS.failWrite=true;assert(!pm::saveInaEnabled(true,false));
 InternalFS.failWrite=false;assert(pm::saveInaEnabled(true,false));assert(!pm::loadInaEnabled(true));
 puts("PASS: enable defaults, disable/enable persistence, bounded file size, absent FS and write/remove failures");
}
