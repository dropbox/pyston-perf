import os
import shutil
import subprocess
import sys
import time
import traceback

import model

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

    initialized = []
    def gotorev():
        if initialized:
            return

        print "Don't have preexisting build; compiling..."

        status = subprocess.check_output(["git", "status", "--porcelain", "--untracked=no", "--ignore-submodules"], cwd=src_dir)
        assert not status, "Source directory is dirty!"

        subprocess.check_call(["git", "checkout", revision], cwd=src_dir)
        subprocess.check_call(["git", "submodule", "update"], cwd=src_dir)

        os.utime(os.path.join(src_dir, "CMakeLists.txt"), None)

        initialized.append(None)

    r = None
    for build_type in ["pyston_release", "pyston_dbg"]:
        this_save_dir = os.path.join(save_dir, build_type)
        if not os.path.exists(this_save_dir):
            os.makedirs(this_save_dir)

        dest_fn = os.path.join(this_save_dir, "pyston")
        if build_type == "pyston_release":
            r = dest_fn

        if os.path.exists(dest_fn):
            continue

        gotorev()

        subprocess.call(["make", build_type], cwd=src_dir)
        subprocess.check_call(["make", build_type], cwd=src_dir)

        build_dir = os.path.join(src_dir, "..", "pyston-build-" + build_type.split('_', 1)[1])
        for d in ["lib_pyston", "from_cpython"]:
            shutil.copytree(os.path.join(build_dir, d), os.path.join(this_save_dir, d))
        shutil.copy(os.path.join(build_dir, "pyston"), dest_fn)
    return r

SRC_DIR = os.path.join(os.path.dirname(__file__), "../../pyston")

def run_test(revision, benchmark):
    fn = build(revision, SRC_DIR)
    bm_fn = os.path.abspath(os.path.join(os.path.dirname(__file__), "../benchmarking/benchmark_suite", benchmark))

    run_id = model.add_run(revision, benchmark)
    print "Starting run", run_id

    save_dir = get_run_save_dir(run_id)
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    print fn, bm_fn
    print "In %r" % save_dir

    start = time.time()
    run_perf = True
    args = [fn, "-ps", bm_fn]
    if run_perf:
        args = ["perf", "record", "-g", "-o", "perf.data", "--"] + args

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

def compare(rev1, rev2, benchmark):
    rev1_pretty = rev1[:18]
    rev2_pretty = rev2[:18]
    rev1 = subprocess.check_output(["git", "rev-parse", rev1], cwd=SRC_DIR).strip()
    rev2 = subprocess.check_output(["git", "rev-parse", rev2], cwd=SRC_DIR).strip()

    for r in model.get_runs(rev1, benchmark) + model.get_runs(rev2, benchmark):
        if not hasattr(r.md, "exitcode"):
            print "Removing unfinished benchmark run %d" % r.id
            remove_run(r.id)

    while True:
        runs1 = model.get_runs(rev1, benchmark)
        runs2 = model.get_runs(rev2, benchmark)

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
            elif cmd == 'p':
                assert len(args) == 1
                run_id = int(args[0])
                subprocess.check_call(["perf", "report", "-n", "-i", get_run_save_dir(run_id) + "/perf.data"])
            elif cmd == 'q':
                break
            else:
                print "Unknown command %r" % cmd
        except Exception:
            traceback.print_exc()

    return

    runs1 = model.get_runs(rev1, benchmark)
    runs2 = model.get_runs(rev2, benchmark)

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

if __name__ == "__main__":
    assert len(sys.argv) == 3
    rev1 = sys.argv[1]
    rev2 = sys.argv[2]

    compare(rev1, rev2, "raytrace.py")

# print build(MASTER_REV, SRC_DIR)
# run_test(MASTER_REV, "django-template.py")
