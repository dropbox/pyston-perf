#!/usr/bin/env python

import argparse
import commands
import os.path
import subprocess
import time

import codespeed_submit
import model

def run_tests(executables, benchmarks, filters, callbacks, benchmark_dir):
    times = [[] for e in executables]

    for b in benchmarks:
        for e, time_list in zip(executables, times):
            skip = False
            for f in filters:
                if f(e, b):
                    skip = True
                    break

            if skip:
                print "%s %s: skipped" % (e.name.rjust(15), b.ljust(35))
                continue

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
    parser.add_argument("--save", dest="save_report", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--compare", dest="compare_to", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--clear", dest="clear", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--skip_repeated", dest="skip_repeated", action="store_true")
    parser.add_argument("--save_by_commit", dest="save_by_commit", action="store_true")
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
        "nbody.py",
        "fannkuch.py",
        "chaos.py",
        "spectral_norm.py",
        ]]

    callbacks = []
    filters = []

    git_rev = None

    if args.submit:
        git_rev = git_rev or get_git_rev(args.pyston_dir)
        def submit_callback(exe, benchmark, elapsed):
            benchmark = os.path.basename(benchmark)

            assert benchmark.endswith(".py")
            benchmark = benchmark[:-3]

            commitid = git_rev
            if "cpython" in exe.name:
                commitid = "default"
            codespeed_submit.submit(commitid=commitid, benchmark=benchmark, executable=exe.name, value=elapsed)
        callbacks.append(submit_callback)

    if args.save_by_commit:
        git_rev = git_rev or get_git_rev(args.pyston_dir)
        def save_callback(exe, benchmark, elapsed):
            report_name = "%s_%s" % (exe.name, git_rev)
            model.save_result(report_name, benchmark, elapsed)
        callbacks.append(save_callback)

    if args.compare_to:
        report_name = args.compare_to
        print "Comparing to '%s'" % report_name
        def compare_callback(exe, benchmark, elapsed):
            v = model.get_result(report_name, benchmark)
            if v is None:
                print "(no previous)",
            else:
                print "Previous: %.1f (%+0.1f%%)" % (v, (elapsed - v) / v * 100),
        callbacks.append(compare_callback)

    if args.save_report:
        report_name = args.save_report
        print "Saving results as '%s'" % report_name
        def save_report_callback(exe, benchmark, elapsed):
            model.save_result(report_name, benchmark, elapsed)
        callbacks.append(save_report_callback)

    if args.skip_repeated:
        git_rev = git_rev or get_git_rev(args.pyston_dir)
        def repeated_filter(exe, benchmark):
            v = model.get_result("%s_%s" % (exe.name, git_rev), benchmark)
            if v:
                return True
            return False
        filters.append(repeated_filter)

    run_tests(executables, benchmarks, filters, callbacks, args.pyston_dir)

if __name__ == "__main__":
    main()
