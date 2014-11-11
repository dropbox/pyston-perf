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
                skip = f(e, b)
                if isinstance(skip, float) or skip:
                    break

            if not isinstance(skip, float) and skip:
                print "%s %s: skipped" % (e.name.rjust(15), b.ljust(35))
                continue

            if isinstance(skip, float):
                elapsed = skip
            else:
                start = time.time()

                args = e.args + [os.path.join(benchmark_dir, b)]
                if b == "(calibration)":
                    args = ["python", os.path.join(benchmark_dir, "minibenchmarks/fannkuch_med.py")]
                subprocess.check_call(args, stdout=open("/dev/null", 'w'))
                elapsed = time.time() - start

            print "%s %s: % 6.1fs" % (e.name.rjust(15), b.ljust(35), elapsed),

            time_list.append(elapsed)

            for cb in callbacks:
                cb(e, b, elapsed)

            print

    for e, time_list in zip(executables, times):
        t = 1
        for elapsed in time_list:
            t *= elapsed
        t **= (1.0 / len(time_list))
        print "%s %s: % 6.1fs" % (e.name.rjust(15), "(geomean)".ljust(35), t),
        for cb in callbacks:
            cb(e, "(geomean)", t)
        print


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
    parser.add_argument("--no-run-pyston", dest="run_pyston", action="store_false", default=True)
    parser.add_argument("--run-cpython", dest="run_cpython", action="store_true")
    parser.add_argument("--save", dest="save_report", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--compare", dest="compare_to", action="append", nargs="?", default=None, const="tmp")
    parser.add_argument("--clear", dest="clear", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--skip-repeated", dest="skip_repeated", action="store_true")
    parser.add_argument("--save-by-commit", dest="save_by_commit", action="store_true")
    parser.add_argument("--view", dest="view", action="store", nargs="?", default=None, const="last")
    args = parser.parse_args()

    if args.clear:
        model.clear_report(args.clear)
        return

    executables = []

    if args.pyston_dir is None:
        args.pyston_dir = os.path.join(os.path.dirname(__file__), "../../pyston")

    if args.run_pyston:
        pyston_executable = os.path.join(args.pyston_dir, "src/pyston_release")
        if not args.view:
            assert os.path.exists(pyston_executable)
        executables.append(Executable([pyston_executable, "-q"], "pyston"))

    if args.run_cpython:
        python_executable = "python"
        python_name = commands.getoutput(python_executable +
                " -c 'import sys; print \"cpython %d.%d\" % (sys.version_info.major, sys.version_info.minor)'")
        executables.append(Executable(["python"], python_name))
    # if RUN_PYPY:
        # executables.append(Executable(["python"], "cpython 2.7"))

    only_pyston = args.run_pyston and len(executables) == 1

    benchmarks = ["(calibration)"]

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

    if args.view:
        def view_filter(exe, benchmark):
            v = model.get_result(args.view, benchmark)
            if v is not None:
                return v
            return True
        filters.append(view_filter)

    if args.submit:
        def submit_callback(exe, benchmark, elapsed):
            benchmark = os.path.basename(benchmark)

            if benchmark.endswith(".py"):
                benchmark = benchmark[:-3]
            else:
                assert benchmark in ("(geomean)", "(calibration)")

            if "cpython" in exe.name:
                commitid = "default"
            else:
                commitid = get_git_rev(args.pyston_dir)
            codespeed_submit.submit(commitid=commitid, benchmark=benchmark, executable=exe.name, value=elapsed)
        callbacks.append(submit_callback)

    if args.save_by_commit:
        assert only_pyston
        git_rev = git_rev or get_git_rev(args.pyston_dir)
        def save_callback(exe, benchmark, elapsed):
            report_name = "%s_%s" % (exe.name, git_rev)
            model.save_result(report_name, benchmark, elapsed)
        callbacks.append(save_callback)

    if args.compare_to:
        print "Comparing to '%s'" % args.compare_to
        def compare_callback(exe, benchmark, elapsed):
            for report_name in args.compare_to:
                v = model.get_result(report_name, benchmark)
                if v is None:
                    print "(no %s)" % report_name,
                else:
                    print "%s: %.1f (%+0.1f%%)" % (report_name, v, (elapsed - v) / v * 100),
        callbacks.append(compare_callback)

    if args.save_report:
        assert len(executables) == 1, "Can't save a run on multiple executables"

        if not args.skip_repeated and args.save_report != args.view:
            model.clear_report(args.save_report)
        print "Saving results as '%s'" % args.save_report
        def save_report_callback(exe, benchmark, elapsed):
            model.save_result(args.save_report, benchmark, elapsed)
        callbacks.append(save_report_callback)

    tmp_results = []
    def save_last_callback(exe, benchmark, elapsed):
        tmp_results.append((exe, benchmark, elapsed))
    callbacks.append(save_last_callback)

    if args.skip_repeated:
        if args.save_report:
            skip_report_name = lambda exe: args.save_report
        else:
            git_rev = git_rev or get_git_rev(args.pyston_dir)
            skip_report_name = lambda exe: "%s_%s" % (exe.name, git_rev)
        def repeated_filter(exe, benchmark):
            v = model.get_result(skip_report_name(exe), benchmark)
            if v:
                return v
            return False
        filters.append(repeated_filter)

    try:
        run_tests(executables, benchmarks, filters, callbacks, args.pyston_dir)
    except KeyboardInterrupt:
        print "Interrupted"
    finally:
        model.clear_report("last")
        print "Saving results to 'last'"
        for (exe, benchmark, elapsed) in tmp_results:
            model.save_result("last", benchmark, elapsed)

if __name__ == "__main__":
    main()
