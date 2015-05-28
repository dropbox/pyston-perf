import os
import sys
import subprocess

assert not os.path.exists("bench_env")

VIRTUALENV_SCRIPT = os.path.dirname(__file__) + "/lib/virtualenv/virtualenv.py"
WHEEL = os.path.dirname(__file__) + "/lib/requests-2.7.0-py2.py3-none-any.whl"

try:
    args = [sys.executable, VIRTUALENV_SCRIPT, "-p", sys.executable, "bench_env"]
    print "Running", args
    subprocess.check_call(args)

    args = ["bench_env/bin/pip", "install", WHEEL]
    print "Running", args
    subprocess.check_call(args)

    assert os.path.exists("bench_env")

    print "PASSED"
finally:
    subprocess.call(["rm", "-rf", "bench_env"])
