import os
import shutil
import subprocess
import sys
import time
import traceback

import model

CONFIGURATION = "pyston_release"

try:
    import readline # this actually activates readline
    readline # silence pyflakes
except ImportError:
    pass

def get_build_save_dir(revision):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_builds", revision)

def get_run_save_dir(run_id):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_runs", str(run_id))

def build(revision, src_dir):
    assert len(revision) == 40, "Please provide a full sha1 hash"

    print "Getting build for %r..." % revision

    save_dir = get_build_save_dir(revision)

    on_new_rev = False
    old_revision = []

    def gotorev(rev):
        print "Don't have preexisting build; compiling..."

        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked=no", "--ignore-submodules"], cwd=src_dir)
        assert not status, "Source directory is dirty!"

        old_revision.append(subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=src_dir).strip())

        subprocess.check_call(["git", "checkout", rev], cwd=src_dir)
        subprocess.check_call(["git", "submodule", "update"], cwd=src_dir)

        os.utime(os.path.join(src_dir, "CMakeLists.txt"), None)

    try:
        r = None

        build_types = [CONFIGURATION]
        # build_types = ["pyston_release", "pyston_dbg"]

        for build_type in build_types:
            this_save_dir = os.path.join(save_dir, build_type)
            if not os.path.exists(this_save_dir):
                os.makedirs(this_save_dir)

            dest_fn = os.path.join(this_save_dir, "pyston")
            if build_type == CONFIGURATION:
                r = dest_fn

            if os.path.exists(dest_fn):
                continue

            if not on_new_rev:
                on_new_rev = True
                gotorev(revision)

            code = subprocess.call(["git", "merge-base", "--is-ancestor", "bafb715", revision], cwd=src_dir)
            # If code==0, then this is past the change to move the build directory
            old_pyston_build_dir = (code!=0)

            subprocess.call(["make", build_type], cwd=src_dir)
            subprocess.check_call(["make", build_type], cwd=src_dir)

            if old_pyston_build_dir:
                build_dir = os.path.join(src_dir, "..", "pyston-build-" + build_type.split('_', 1)[1])
            else:
                build_names = {
                        "pyston_release": "Release",
                        "pyston_pgo": "Release-gcc-pgo",
                        }
                build_dir = os.path.join(src_dir, "build", build_names[build_type])
            assert os.path.exists(build_dir), build_dir
            for d in ["lib_pyston", "from_cpython"]:
                shutil.copytree(os.path.join(build_dir, d), os.path.join(this_save_dir, d))
            shutil.copy(os.path.join(build_dir, "pyston"), dest_fn)
        return r
    finally:
        if on_new_rev and old_revision:
            gotorev(old_revision[0])

SRC_DIR = os.path.join(os.path.dirname(__file__), "../../pyston")
BENCHMARKS_DIR = os.path.join(os.path.dirname(__file__), "../benchmarking/benchmark_suite")

def run_test(revision, benchmark):
    fn = build(revision, SRC_DIR)
    bm_fn = os.path.abspath(os.path.join(BENCHMARKS_DIR, benchmark))

    run_id = model.add_run(revision, CONFIGURATION, benchmark)
    print "Starting run", run_id

    save_dir = get_run_save_dir(run_id)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print fn, bm_fn
    print "In %r" % save_dir

    run_perf = True
    args = [fn, "-s", bm_fn]
    if run_perf:
        args = ["perf", "record", "-g", "-o", "perf.data", "--"] + args

    start = time.time()
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=save_dir)
    out, err = p.communicate()
    exitcode = p.wait()
    elapsed = time.time() - start

    model.set_metadata(run_id, "has_perf", run_perf)
    model.set_metadata(run_id, "elapsed", elapsed)
    model.set_metadata(run_id, "exitcode", exitcode)

    with open(os.path.join(save_dir, "out.log"), 'w') as f:
        f.write(out)

    with open(os.path.join(save_dir, "err.log"), 'w') as f:
        f.write(err)

    print "Took %.1fs, and exited with code %s" % (elapsed, exitcode)
    if exitcode != 0:
        print out
        print err

    return run_id

def remove_run(run_id):
    print "Removing run", run_id
    model.delete_run(run_id)
    shutil.rmtree(get_run_save_dir(run_id))

def compareBenchmark(rev1, rev2, benchmark):
    rev1_pretty = rev1[:18]
    rev2_pretty = rev2[:18]
    rev1 = subprocess.check_output(["git", "rev-parse", rev1], cwd=SRC_DIR).strip()
    rev2 = subprocess.check_output(["git", "rev-parse", rev2], cwd=SRC_DIR).strip()

    if '.' not in benchmark:
        benchmark += ".py"
    assert benchmark.endswith(".py")
    assert os.path.exists(os.path.join(BENCHMARKS_DIR, benchmark))

    for r in get_runs(rev1, benchmark) + get_runs(rev2, benchmark):
        if not hasattr(r.md, "exitcode"):
            print "Removing unfinished benchmark run %d" % r.id
            remove_run(r.id)

    while True:
        runs1 = get_runs(rev1, benchmark)
        runs2 = get_runs(rev2, benchmark)

        fmt1 = [r.format() for r in runs1]
        fmt2 = [r.format() for r in runs2]
        while len(fmt1) < len(fmt2):
            fmt1.append("")
        while len(fmt1) > len(fmt2):
            fmt2.append("")
        print "% 19s: % 19s:" % (rev1_pretty, rev2_pretty)
        for f1, f2 in zip(fmt1, fmt2):
            print "% 20s % 20s" % (f1, f2)

        print
        print "Commands:"
        print "a: do 2 more runs of %s" % rev1_pretty
        print "b: do 2 more runs of %s" % rev2_pretty
        print "delete RUN_ID: delete run"
        print "p RUN_ID: go to perf report"
        cmd = raw_input("What would you like to do? ")
        try:
            args = cmd.split()
            cmd = args[0]
            args = args[1:]
            if cmd == 'a':
                assert not args
                r = run_test(rev1, benchmark)
                remove_run(r)
                run_test(rev1, benchmark)
                run_test(rev1, benchmark)
            elif cmd == 'b':
                assert not args
                r = run_test(rev2, benchmark)
                remove_run(r)
                run_test(rev2, benchmark)
                run_test(rev2, benchmark)
            elif cmd == 'delete':
                assert len(args) == 1
                run_id = int(args[0])
                remove_run(run_id)
            elif cmd == 'p':
                assert len(args) == 1
                run_id = int(args[0])
                subprocess.check_call(["perf", "report", "-n", "-i", get_run_save_dir(run_id) + "/perf.data"])
            elif cmd == 'stderr':
                assert len(args) == 1
                run_id = int(args[0])
                subprocess.check_call(["less", get_run_save_dir(run_id) + "/err.log"])
            elif cmd == 'stdout':
                assert len(args) == 1
                run_id = int(args[0])
                subprocess.check_call(["less", get_run_save_dir(run_id) + "/err.log"])
            elif cmd == 'pd':
                assert len(args) == 2
                run_id1 = int(args[0])
                run_id2 = int(args[1])
                subprocess.check_call("perf report -i %s/perf.data -n --no-call-graph | bash %s/tools/cumulate.sh > perf1.txt" % (get_run_save_dir(run_id1), SRC_DIR), shell=True)
                subprocess.check_call("perf report -i %s/perf.data -n --no-call-graph | bash %s/tools/cumulate.sh > perf2.txt" % (get_run_save_dir(run_id2), SRC_DIR), shell=True)
                subprocess.check_call(["python", "%s/tools/perf_diff.py" % SRC_DIR, "perf1.txt", "perf2.txt"])
            elif cmd == 'q':
                break
            else:
                print "Unknown command %r" % cmd
        except Exception:
            traceback.print_exc()

    return

    runs1 = get_runs(rev1, benchmark)
    runs2 = get_runs(rev2, benchmark)

    elapsed1 = []
    elapsed2 = []
    print "Baseline:"
    for r in runs1:
        e = float(model.get_metadata(r, "elapsed"))
        print r, e
        elapsed1.append(e)
    print "Update:"
    for r in runs2:
        e = float(model.get_metadata(r, "elapsed"))
        print r, e
        elapsed2.append(e)
    print "Min time: %+.1f%%" % ((min(elapsed2) / min(elapsed1) - 1) * 100.0)
    print "Avg time: %+.1f%%" % ((sum(elapsed2) / len(elapsed2) / sum(elapsed1) * len(elapsed1)- 1) * 100.0)
    print runs1, runs2

BENCHMARKS = [
    "django_template3.py",
    "pyxl_bench.py",
    "sqlalchemy_imperative2.py",
    ]

UNAVERAGED_BENCHMARKS = [
    "django_template2.py",
    "django_template.py",
    "django_lexing.py",
    "django_migrate.py",
    "virtualenv_bench.py",
    ]

# BENCHMARKS += UNAVERAGED_BENCHMARKS

MICROBENCHMARKS = [
    "interp2.py",
    "raytrace.py",
    "nbody.py",
    "fannkuch.py",
    # "chaos.py",
    "fasta.py",
    "pidigits.py",
    "richards.py",
    "deltablue.py",
    "sre_compile_ubench.py",
    ]

# BENCHMARKS += MICROBENCHMARKS

def get_runs(rev, benchmark=None):
    raw_runs = model.get_runs(rev, CONFIGURATION, benchmark)
    rtn = []
    for r in raw_runs:
        save_dir = get_run_save_dir(r.id)
        if not os.path.exists(save_dir):
            model.delete_run(r.id)
        else:
            rtn.append(r)
    return rtn

def compareAll(rev1, rev2):
    rev1_pretty = rev1[:18]
    rev2_pretty = rev2[:18]
    rev1 = subprocess.check_output(["git", "rev-parse", rev1], cwd=SRC_DIR).strip()
    rev2 = subprocess.check_output(["git", "rev-parse", rev2], cwd=SRC_DIR).strip()

    for r in get_runs(rev1) + get_runs(rev2):
        if not hasattr(r.md, "exitcode"):
            print "Removing unfinished benchmark run %d" % r.id
            remove_run(r.id)

    class Stats(object):
        def __init__(self):
            self.__results = []

        def add(self, run):
            if run.md.exitcode == 0:
                self.__results.append(run.md.elapsed)

        def count(self):
            return len(self.__results)

        def min(self):
            return min(self.__results)

        def format(self):
            if not self.__results:
                return "N/A"
            return "%.1fs (%d)" % (self.min(), self.count())

    while True:
        stats1 = {b:Stats() for b in BENCHMARKS}
        stats2 = {b:Stats() for b in BENCHMARKS}

        for r in get_runs(rev1):
            if r.benchmark in stats1:
                stats1[r.benchmark].add(r)
        for r in get_runs(rev2):
            if r.benchmark in stats2:
                stats2[r.benchmark].add(r)

        print "% 25s % 19s: % 19s:" % ("", rev1_pretty, rev2_pretty)

        prod1 = 1.0
        prod2 = 1.0
        prod_count = 0

        for b in BENCHMARKS:
            s1 = stats1[b]
            s2 = stats2[b]
            print "% 25s % 20s % 20s" % (b, s1.format(), s2.format()),
            if s1.count() and s2.count():
                prod1 *= s1.min()
                prod2 *= s2.min()
                prod_count += 1
                diff = (s2.min() - s1.min()) / (s1.min())
                print " %+0.1f%%" % (100.0 * diff),
            print

        if prod_count:
            geo1 = prod1 ** (1.0 / prod_count)
            geo2 = prod2 ** (1.0 / prod_count)
            print "% 25s % 19.1fs % 19.1fs" % ("geomean", geo1, geo2),
            diff = (geo2 - geo1) / (geo1)
            print " %+0.1f%%" % (100.0 * diff)

        print
        print "Commands:"
        print "a: do 2 more runs of %s" % rev1_pretty
        print "b: do 2 more runs of %s" % rev2_pretty
        print "d BENCH: detailed view of benchmark"
        cmd = raw_input("What would you like to do? ")
        try:
            args = cmd.split()
            cmd = args[0]
            args = args[1:]
            if cmd in ['a', 'b', 'A', 'B']:
                assert not args
                rev = rev1 if (cmd.lower() == 'a') else rev2
                stats = stats1 if (cmd.lower() == 'a') else stats2
                for b in BENCHMARKS:
                    if cmd.islower() or stats[b].count() < 2:
                        r = run_test(rev, b)
                        remove_run(r)
                        run_test(rev, b)
                        run_test(rev, b)
            elif cmd == 'd':
                assert len(args) == 1
                b = args[0]
                compareBenchmark(rev1_pretty, rev2_pretty, b)
            elif cmd == 'q':
                break
            else:
                print "Unknown command %r" % cmd
        except Exception:
            traceback.print_exc()



if __name__ == "__main__":
    if sys.argv[1] == '--pgo':
        CONFIGURATION = "pyston_pgo"
        del sys.argv[1]

    assert len(sys.argv) in (3,4)
    rev1 = sys.argv[1]
    rev2 = sys.argv[2]

    if len(sys.argv) == 3:
        compareAll(rev1, rev2)
    else:
        compareBenchmark(rev1, rev2, sys.argv[3])

# print build(MASTER_REV, SRC_DIR)
# run_test(MASTER_REV, "django-template.py")
