from pathlib import Path
import hashlib
import importlib.util
import shutil
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('patch',root/'scripts/pm_bounded_wire.py')
patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
framework=Path(sys.argv[1]);wire=framework/'libraries/Wire/Wire_nRF52.cpp'
original=wire.read_bytes();result=patch.patch_source(original.decode())
assert result.count('if(!pmBoundedTwimWait(')==8
assert 'return 0;' in result and 'return 4;' in result
try:patch.patch_source(result)
except RuntimeError:pass
else:raise AssertionError('Must reject changed/already-patched upstream')
with tempfile.TemporaryDirectory() as folder:
    project=Path(folder);target=project/'examples/simple_repeater';target.mkdir(parents=True)
    shutil.copy2(root/'firmware/BoundedWireWait.h',target/'BoundedWireWait.h')
    patch.prepare(framework,project);patch.prepare(framework,project)
    header=(project/'lib/PMBoundedWire/Wire.h').read_text()
    assert header.count('uint32_t pmWireTimeoutCount();')==1
assert wire.read_bytes()==original
print('PASS: all eight I2C waits patched, upstream mismatch rejected, repeatable project-local generation; global core unchanged')
