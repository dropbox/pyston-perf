#!/usr/bin/env python

import argparse
import commands
import os.path
import subprocess
import time

import codespeed_submit
import model

def run_tests(executables, benchmarks, callbacks, benchmark_dir):
    times = [[] for e in executables]

    for b in benchmarks:
        for e, time_list in zip(executables, times):
            start = time.time()
            subprocess.check_call(e.args + [os.path.join(benchmark_dir, b)], stdout=open("/dev/null", 'w'))
            elapsed = time.time() - start

            print "%s %s: % 4.1fs" % (e.name.rjust(15), b.ljust(35), elapsed),

            time_list.append(elapsed)

            for cb in callbacks:
                cb(e, b, elapsed)

            print

    for e, time_list in zip(executables, times):
        t = 1
        for elapsed in time_list:
            t *= elapsed
        t **= (1.0 / len(time_list))
        print "%s %s: % 4.1fs" % (e.name.rjust(15), "geomean".ljust(35), t)


class Executable(object):
    def __init__(self, args, name):
        self.args = args
        self.name = name

def get_git_rev(src_dir):
    p = subprocess.Popen(["git", "status", "--porcelain", "--untracked=no"], cwd=src_dir, stdout=subprocess.PIPE)
    out, err = p.communicate()
    assert not out, "Dirty working tree detected!"
    assert p.poll() == 0

    p = subprocess.Popen(["git", "rev-parse", "HEAD"], cwd=src_dir, stdout=subprocess.PIPE)
    out, err = p.communicate()
    assert p.poll() == 0
    return out.strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pyston_dir", dest="pyston_dir", action="store", default=None)
    parser.add_argument("--submit", dest="submit", action="store_true")
    parser.add_argument("--run_pyston", dest="run_pyston", action="store_false")
    parser.add_argument("--run_cpython", dest="run_cpython", action="store_true")
    parser.add_argument("--result_name", dest="result_name", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--compare", dest="compare_to", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--clear", dest="clear", action="store", nargs="?", default=None, const="tmp")
    # parser.add_argument("--result_name", dest="result_name", action=TestAction)
    args = parser.parse_args()

    if args.clear:
        pass

    executables = []

    if args.run_pyston:
        if args.pyston_dir is None:
            args.pyston_dir = os.path.join(os.path.dirname(__file__), "../../pyston")
        pyston_executable = os.path.join(args.pyston_dir, "src/pyston_release")
        assert os.path.exists(pyston_executable)
        executables.append(Executable([pyston_executable, "-q"], "pyston"))

    if args.run_cpython:
        python_executable = "python"
        python_name = commands.getoutput(python_executable +
                " -c 'import sys; print \"cpython %d.%d\" % (sys.version_info.major, sys.version_info.minor)'")
        executables.append(Executable(["python"], python_name))
    # if RUN_PYPY:
        # executables.append(Executable(["python"], "cpython 2.7"))

    benchmarks = []

    benchmarks += ["microbenchmarks/%s" % (s,) for s in [
        ]]

    benchmarks += ["minibenchmarks/%s" % (s,) for s in [
        "fannkuch_med.py",
        "nbody_med.py",
        "interp2.py",
        "raytrace.py",
        "chaos.py",
        "nbody.py",
        "fannkuch.py",
        "spectral_norm.py",
        ]]

    callbacks = []
    if args.submit:
        git_rev = get_git_rev(args.pyston_dir)
        def submit_callback(exe, benchmark, elapsed):
            benchmark = os.path.basename(benchmark)

            assert benchmark.endswith(".py")
            benchmark = benchmark[:-3]

            commitid = git_rev
            if "cpython" in exe.name:
                commitid = "default"
            codespeed_submit.submit(commitid=commitid, benchmark=benchmark, executable=exe.name, value=elapsed)
        callbacks.append(submit_callback)

    run_tests(executables, benchmarks, callbacks, args.pyston_dir)

if __name__ == "__main__":
    main()
