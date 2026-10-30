#pragma once
#include <stdint.h>
#include <string.h>
#include <openssl/evp.h>
namespace mesh {class Identity {
  uint8_t key[32];
public:
  explicit Identity(const uint8_t* p){memcpy(key,p,32);}
  bool verify(const uint8_t* signature,const uint8_t* bytes,int size) {
    auto pub=EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519,nullptr,key,32);
    auto ctx=EVP_MD_CTX_new();EVP_DigestVerifyInit(ctx,nullptr,nullptr,nullptr,pub);
    bool ok=EVP_DigestVerify(ctx,signature,64,bytes,size)==1;
    EVP_MD_CTX_free(ctx);EVP_PKEY_free(pub);return ok;
  }
};}
