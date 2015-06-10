# A simpler version of virtualenv_bench that tries to reduce the amount of
# subprocess usage.  Intended mostly for perf debugging.

import os
import sys
import subprocess

assert not os.path.exists("bench_env"), subprocess.call(["rm", "-rf", "bench_env"])

VIRTUALENV_SCRIPT = os.path.dirname(__file__) + "/lib/virtualenv/virtualenv.py"
WHEEL = os.path.dirname(__file__) + "/lib/requests-2.7.0-py2.py3-none-any.whl"

import runpy

try:
    sys.argv = [VIRTUALENV_SCRIPT, "-p", sys.executable, "bench_env"]
    sys.path.insert(0, os.path.dirname(VIRTUALENV_SCRIPT))
    execfile(VIRTUALENV_SCRIPT)

    print "PASSED"
finally:
    subprocess.call(["rm", "-rf", "bench_env"])
