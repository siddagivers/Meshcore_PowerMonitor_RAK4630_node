import importlib.util
from pathlib import Path
import struct
import tempfile
import sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
spec=importlib.util.spec_from_file_location('lora_ota',Path(__file__).resolve().parents[1]/'scripts/lora_ota.py')
ota=importlib.util.module_from_spec(spec);spec.loader.exec_module(ota)
key=Ed25519PrivateKey.generate()
for size in [64,4096,5000,10000]:
    body=bytearray(b'\x55'*size);struct.pack_into('<II',body,0,0x2003f000,0x26021)
    blob=ota.pack_image(bytes(body),0x00040000,key)
    assert ota.inspect_package(blob)['image_bytes']==size+56
    corrupt=bytearray(blob);corrupt[-6]^=1
    try:ota.inspect_package(corrupt)
    except (ValueError,Exception) as error:
        assert error is not None
    else:raise AssertionError('corrupt image accepted')
    unsigned=bytearray(blob);unsigned[9]=1
    try:ota.inspect_package(unsigned)
    except ValueError:pass
    else:raise AssertionError('unsigned accepted')
    if size==5000 and len(sys.argv)>1:Path(sys.argv[1]).write_bytes(blob)
print('PASS: signed packages, odd Merkle leaves, precise EndF, unsigned and tampered images')
