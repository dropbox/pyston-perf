import os
import sys
import subprocess

assert not os.path.exists("test_env")

VIRTUALENV_SCRIPT = os.path.dirname(__file__) + "/lib/virtualenv/virtualenv.py"
WHEEL = os.path.dirname(__file__) + "/lib/requests-2.7.0-py2.py3-none-any.whl"

args = [sys.executable, VIRTUALENV_SCRIPT, "-p", sys.executable, "test_env"]
print "Running", args
subprocess.check_call(args)

args = ["test_env/bin/pip", "install", WHEEL]
print "RUnning", args
subprocess.check_call(args)

assert os.path.exists("test_env")
print "Removing the 'test_env/' directory"
subprocess.check_call(["rm", "-rf", "test_env"])

print
print "PASSED"
