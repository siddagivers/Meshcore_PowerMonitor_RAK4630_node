#pragma once
#include <stdint.h>
#include <string.h>
#include <openssl/evp.h>
namespace mesh {struct Utils {
  static void sha256(uint8_t* out,int size,const uint8_t* a,int n,const uint8_t* b=nullptr,int m=0) {
    auto ctx=EVP_MD_CTX_new();unsigned length;uint8_t hash[32];
    EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr);EVP_DigestUpdate(ctx,a,n);
    if(b)EVP_DigestUpdate(ctx,b,m);
    EVP_DigestFinal_ex(ctx,hash,&length);EVP_MD_CTX_free(ctx);memcpy(out,hash,size);
  }
};}
