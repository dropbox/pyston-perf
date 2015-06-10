import os
import shutil
import subprocess
import time

import model

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
    runs1 = model.get_runs(rev1, benchmark)
    runs2 = model.get_runs(rev2, benchmark)
    print runs1, runs2
    assert runs1
    assert runs2
    if not runs1:
        r = run_test(rev1, benchmark)
        remove_run(r)
        run_test(rev1, benchmark)
        run_test(rev1, benchmark)
    if not runs2:
        r = run_test(rev2, benchmark)
        remove_run(r)
        run_test(rev2, benchmark)
        run_test(rev2, benchmark)

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

MASTER_REV = "268f275f4cfe42f2562687107bf3c9ca5afd809b"
PASS_BOXES_REV = "f2c705de01022d8dd965423753b71913cc2df900"
PASS_BOXES_BASELINE_REV = "3a5b3e50e749ded943e7327dc3386c66486a8099"

compare(PASS_BOXES_BASELINE_REV, PASS_BOXES_REV, "raytrace.py")

# print build(MASTER_REV, SRC_DIR)
# run_test(MASTER_REV, "django-template.py")
