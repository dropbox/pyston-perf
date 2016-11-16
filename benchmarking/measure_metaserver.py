
import json
import os
import shutil
import subprocess

import codespeed_submit

BENCHMARK_SCRIPT = "/srv/server/test_metaserver_perf.py"
assert os.path.exists(BENCHMARK_SCRIPT)

CPYTHON = False

def get_git_rev(allow_dirty):
    src_dir = "/home/vagrant/pyston"

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
    git_rev = get_git_rev(False)
    shutil.copy("/home/vagrant/pyston/pyston_release", "/home/vagrant/encap-staging/pyston-env/bin/")


    def do_run():
        args = ["python", BENCHMARK_SCRIPT, "--perf-tracking"]
        if CPYTHON:
            args.append("--cpython")
        o = subprocess.check_output(args)
        return json.loads(o)
        # return {u'metaserver_c5f2b83b_second10': 0.6009996891021728, u'metaserver_c5f2b83b_first10': 0.994839096069336, u'metaserver_c5f2b83b_startup': 15.275195121765137}

    # Warmup:
    print "Doing warmup run..."
    print do_run()

    NRUNS = 8
    results = {}
    print "Did warmup run, doing %d real runs and averaging..." % NRUNS

    for i in xrange(NRUNS):
        r = do_run()
        print r
        for k, v in r.items():
            results[k] = results.get(k, 0) + v

    for k, v in results.items():
        name = "cpython 2.7" if CPYTHON else "pyston"
        codespeed_submit.submit(git_rev, str(k), name, v / NRUNS)

if __name__ == "__main__":
    main()
