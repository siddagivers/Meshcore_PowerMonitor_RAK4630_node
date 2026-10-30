#pragma once
#include <stddef.h>
#include <stdint.h>
namespace pm {
// Commands are reachable only from local USB or upstream authenticated admin CLI.
bool otaCommand(const char* command,char* reply,size_t cap,bool local);
void otaPoll(bool radioPending);
}
