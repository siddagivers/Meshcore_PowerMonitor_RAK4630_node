#pragma once
#include <stdint.h>
#include <string.h>
#include <openssl/evp.h>
class SHA256 {
  EVP_MD_CTX* ctx=EVP_MD_CTX_new();
public:
  SHA256(){EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr);}
  ~SHA256(){EVP_MD_CTX_free(ctx);}
  void update(const void* p,size_t n){EVP_DigestUpdate(ctx,p,n);}
  void finalize(void* p,size_t n){uint8_t hash[32];unsigned len;EVP_DigestFinal_ex(ctx,hash,&len);memcpy(p,hash,n);}
};
