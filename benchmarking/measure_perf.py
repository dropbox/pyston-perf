#!/usr/bin/env python

import argparse
import commands
import hashlib
import os.path
import re
import subprocess
import sys
import time

import codespeed_submit
import model

EXE_LEN = 20

def run_tests(executables, benchmarks, filters, callbacks, benchmark_dir):
    times = [[] for e in executables]
    failed = [False for e in executables]

    for b in benchmarks:
        for i, e in enumerate(executables):
            skip = False
            for f in filters:
                skip = f(e, b.filename)
                if isinstance(skip, float) or skip:
                    break

            if not isinstance(skip, float) and skip:
                # print "%s %s: skipped" % (e.name.rjust(EXE_LEN), b.filename.ljust(35))
                failed[i] = True
                continue

            take_min = e.opts.get("take_min")
            if isinstance(skip, float) and not take_min:
                elapsed = skip
                code = 0
            else:
                code = 0

                if e.opts.get("clear_cache"):
                    subprocess.check_call(["rm", "-rf", os.path.expanduser("~/.cache/pyston")])

                args = e.args + [os.path.join(benchmark_dir, b.filename)]
                if b.filename == "(calibration)":
                    args = ["python", os.path.join(benchmark_dir, "fannkuch_med.py")]

                if isinstance(skip, float):
                    # print "Previous min was", skip
                    elapsed = skip
                else:
                    elapsed = float('inf')

                # Warmup:
                for _ in xrange(e.opts.get('run_times', 1) - 1):
                    start = time.time()
                    code = subprocess.call(args, stdout=open("/dev/null", 'w'))
                    if code == 0:
                        _e = time.time() - start
                        if take_min:
                            # print _e
                            elapsed = min(elapsed, _e)

                start = time.time()
                code = subprocess.call(args, stdout=open("/dev/null", 'w'))
                _e = time.time() - start
                if take_min:
                    # print _e
                    elapsed = min(elapsed, _e)
                else:
                    elapsed = _e

            if code != 0:
                print "%s %s: failed (code %d)" % (e.name.rjust(EXE_LEN), b.filename.ljust(35), code),
                failed[i] = True
            else:
                print "%s %s: % 6.2fs" % (e.name.rjust(EXE_LEN), b.filename.ljust(35), elapsed),

                times[i].append(elapsed)

                for cb in callbacks:
                    cb(e, b.filename, elapsed)

            print

    geomean_str = " ".join(sorted([os.path.basename(b.filename) for b in benchmarks if b.include_in_average]))
    geomean_name = "(geomean-%s)" % (hashlib.sha1(geomean_str).hexdigest()[:4])

    for i, e in enumerate(executables):
        if failed[i]:
            continue

        time_list = times[i]
        assert len(time_list) == len(benchmarks)
        t = 1
        n = 0
        for j, elapsed in enumerate(time_list):
            if not benchmarks[j].include_in_average:
                continue
            t *= elapsed
            n += 1
        t **= (1.0 / n)
        print "%s %s: % 6.2fs" % (e.name.rjust(EXE_LEN), geomean_name.ljust(35), t),
        for cb in callbacks:
            cb(e, geomean_name, t)
        print


class Executable(object):
    def __init__(self, args, name, opts):
        self.args = args
        self.name = name
        self.opts = opts

class Benchmark(object):
    def __init__(self, filename, include_in_average):
        self.filename = filename
        self.include_in_average = include_in_average

def get_git_rev(src_dir, allow_dirty):
    if not allow_dirty:
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
    parser.add_argument("--run-pyston-interponly", dest="run_pyston_interponly", action="store_true", default=False)
    parser.add_argument("--run-pyston-nocache", dest="run_pyston_nocache", action="store_true", default=False)
    parser.add_argument("--run-cpython", action="store", nargs="?", default=None, const="python")
    parser.add_argument("--run-pypy", action="store", nargs="?", default=None, const="pypy")
    parser.add_argument("--save", dest="save_report", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--compare", dest="compare_to", action="append", nargs="?", default=None, const="tmp")
    parser.add_argument("--clear", dest="clear", action="store", nargs="?", default=None, const="tmp")
    parser.add_argument("--use-previous", action="store_true")
    parser.add_argument("--save-by-commit", dest="save_by_commit", action="store_true")
    parser.add_argument("--view", dest="view", action="store", nargs="?", default=None, const="last")
    parser.add_argument("--allow-dirty", dest="allow_dirty", action="store_true")
    parser.add_argument("--list-reports", dest="list_reports", action="store_true")
    parser.add_argument("--pyston-executables-subdir", dest="pyston_executables_subdir", action="store", default=".")
    parser.add_argument("--pyston-executable", dest="pyston_executable", action="store")
    parser.add_argument("--run-times", dest="run_times", action="store", default='1')
    parser.add_argument("--extra-jit-args", dest="extra_jit_args", action="append")
    parser.add_argument("--take-min", action="store_true")
    parser.add_argument("--benchmark-filter", "--filter", dest="benchmark_filter", action="append")
    args = parser.parse_args()

    if args.list_reports:
        for report_name in model.list_reports():
            print report_name
        return

    if args.clear:
        model.clear_report(args.clear)
        return

    executables = []

    callbacks = []
    filters = []

    if args.pyston_dir is None:
        args.pyston_dir = os.path.join(os.path.dirname(__file__), "../../pyston")

    extra_jit_args = args.extra_jit_args or []

    pyston_executable = args.pyston_executable
    if not pyston_executable:
        pyston_executable = os.path.join(args.pyston_dir, os.path.join(args.pyston_executables_subdir, "pyston_release"))

    if not args.view:
        assert os.path.exists(pyston_executable), pyston_executable

    global_opts = {}
    global_opts['take_min'] = args.take_min

    if args.run_pyston:
        opts = dict(global_opts)
        opts['run_times'] = int(args.run_times)
        executables.append(Executable([pyston_executable] + extra_jit_args, "pyston", opts))

    if args.run_cpython:
        python_executable = args.run_cpython
        python_name = commands.getoutput(python_executable +
                " -c 'import sys; print \"cpython %d.%d\" % (sys.version_info.major, sys.version_info.minor)'")
        executables.append(Executable([python_executable], python_name, global_opts))

    if args.run_pypy:
        pypy_executable = args.run_pypy
        pypy_build = commands.getoutput(pypy_executable +
                " -c 'import platform; print platform.python_build()[0]'")
        pypy_name = "pypy %s" % pypy_build.split('+')[0]
        executables.append(Executable([pypy_executable], pypy_name, global_opts))

    averaged_benchmarks = [
        "django_template2.py",
        "pyxl_bench.py",
        "sqlalchemy_imperative2.py",
        # "django_migrate.py",
        # "virtualenv_bench.py",
        # "interp2.py",
        # "raytrace.py",
        # "nbody.py",
        # "fannkuch.py",
        # "chaos.py",
        # "fasta.py",
        # "pidigits.py",
        # "richards.py",
        # "deltablue.py",
        ]

    unaveraged_benchmarks = [
        "django_template.py",
            ]

    compare_to_interp_benchmarks = [
            "django_migrate.py",
            "sre_parse_parse.py",
            "raytrace_small.py",
            "deltablue.py",
            "richards.py",
            ]

    if args.run_pyston_nocache:
        opts = dict(global_opts)
        opts['clear_cache'] = True
        executables.append(Executable([pyston_executable] + extra_jit_args, "pyston_nocache", opts))

    if args.run_pyston_interponly:
        executables.append(Executable([pyston_executable, "-I"] + extra_jit_args, "pyston_interponly", global_opts))
        unaveraged_benchmarks += set(compare_to_interp_benchmarks).difference(averaged_benchmarks)

        def interponly_filter(exe, benchmark):
            if exe.name != "pyston_interponly":
                return False
            return benchmark not in compare_to_interp_benchmarks
        filters.append(interponly_filter)

    if args.benchmark_filter:
        def benchmark_filter(exe, benchmark):
            return not any([re.search(p, benchmark) for p in args.benchmark_filter])
        filters.append(benchmark_filter)

    benchmarks = ([Benchmark("(calibration)", False)] +
            [Benchmark(b, True) for b in averaged_benchmarks] +
            [Benchmark(b, False) for b in unaveraged_benchmarks])

    benchmark_dir = os.path.join(os.path.dirname(__file__), "benchmark_suite")

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
                assert benchmark == "(calibration)" or benchmark.startswith("(geomean")

            if "cpython" in exe.name.lower():
                commitid = "default"
            elif "pypy" in exe.name.lower():
                commitid = pypy_build
            else:
                commitid = get_git_rev(args.pyston_dir, args.allow_dirty)
            codespeed_submit.submit(commitid=commitid, benchmark=benchmark, executable=exe.name, value=elapsed)
        callbacks.append(submit_callback)

    def report_name_for_exe(exe):
        if "cpython" in exe.name.lower():
            report_name = "cpython"
        elif "pypy" in exe.name.lower():
            report_name = exe.name.lower().replace(' ', '_')
        else:
            assert 'pyston' in exe.name.lower()
            report_name = "%s_%s" % (exe.name, git_rev)
        return report_name

    if args.save_by_commit:
        git_rev = git_rev or get_git_rev(args.pyston_dir, args.allow_dirty)
        def save_callback(exe, benchmark, elapsed):
            report_name = report_name_for_exe(exe)
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
                    print "%s: %.2f (%s%%)" % (report_name, v, "{:5.1f}".format((elapsed - v) / v * 100)),
        callbacks.append(compare_callback)

    if args.save_report:
        assert len(executables) == 1, "Can't save a run on multiple executables"

        if not args.use_previous and args.save_report != args.view:
            model.clear_report(args.save_report)
        print "Saving results as '%s'" % args.save_report
        def save_report_callback(exe, benchmark, elapsed):
            old_val = model.get_result(args.save_report, benchmark)
            model.save_result(args.save_report, benchmark, elapsed)
            if old_val is not None and args.take_min:
                print "(prev min: %.2fs)" % (old_val,),
        callbacks.append(save_report_callback)

    tmp_results = []
    def save_last_callback(exe, benchmark, elapsed):
        tmp_results.append((exe, benchmark, elapsed))
    callbacks.append(save_last_callback)

    if args.use_previous:
        if args.save_report:
            skip_report_name = lambda exe: args.save_report
        else:
            git_rev = git_rev or get_git_rev(args.pyston_dir, args.allow_dirty)
            skip_report_name = report_name_for_exe
        def repeated_filter(exe, benchmark):
            v = model.get_result(skip_report_name(exe), benchmark)
            if v:
                return v
            return False
        filters.append(repeated_filter)

    try:
        run_tests(executables, benchmarks, filters, callbacks, benchmark_dir)
    except KeyboardInterrupt:
        print "Interrupted"
        sys.exit(1)
    finally:
        model.clear_report("last")
        print "Saving results to 'last'"
        for (exe, benchmark, elapsed) in tmp_results:
            model.save_result("last", benchmark, elapsed)

if __name__ == "__main__":
    main()
