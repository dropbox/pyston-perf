import os
import pickle
import subprocess
import sys
import time
import traceback

BENCHMARKS = [
    "django_template.py",
    "pyxl_bench.py",
    "sqlalchemy_imperative2.py",
    ]

SRC_DIR = os.path.join(os.path.dirname(__file__), "../../pyston")
BENCHMARKS_DIR = os.path.join(os.path.dirname(__file__), "../benchmarking/benchmark_suite")
WARMUP_TIMES = 2

CPYTHON_TIMES = {
    "django_template.py": 1479,
    "pyxl_bench.py": 1966,
    "sqlalchemy_imperative2.py": 2056,
}

def collect_stats():
    allstats = {}

    for b in BENCHMARKS:
        run_args = [pyston_exe, "-s", os.path.join(BENCHMARKS_DIR, b)]
        for i in xrange(WARMUP_TIMES):
            print "Warmup #%d of %s" % (i + 1, b)
            subprocess.check_call(run_args, stdout=open("/dev/null"), stderr=open("/dev/null"))

        print "Running %s" % (b,)
        p = subprocess.Popen(run_args, stdout=open("/dev/null"), stderr=subprocess.PIPE)
        out, err = p.communicate()
        r = p.wait()
        assert r == 0, (out, err)

        stats = {}
        _, counter_str = err.split("Counters:")
        counter_str, _ = counter_str.split("(End of stats)")
        for l in counter_str.strip().split('\n'):
            assert l.count(':') == 1, l
            k, v = l.split(':')
            stats[k] = v

        allstats[b] = stats

    return allstats

if __name__ == "__main__":
    pyston_exe = SRC_DIR + "/pyston_release"
    assert os.path.exists(pyston_exe)

    if subprocess.call(["grep", "-q", "STAT_TIMERS (1", os.path.join(SRC_DIR, "src/core/stats.h")]) == 1:
        raise Exception("Stat timers do not seem to be turned on in the source")

    if not os.path.exists("stats.pkl") or os.stat("stats.pkl").st_mtime <= os.stat(pyston_exe).st_mtime:
        allstats = collect_stats()
        with open("stats.pkl", "w") as f:
            pickle.dump(allstats, f)

    allstats = pickle.load(open("stats.pkl"))

    categorizers = []
    categorizers.append(lambda k: (k, 30))
    # categorizers.append(lambda k: ("misc", 0))

    def prefix_categorizer(prefix, name, score):
        def categorizer(k):
            if k.startswith(prefix):
                return name, score
        return categorizer

    def list_categorizer(l, name, score):
        def categorizer(k):
            if k in l:
                return name, score
            assert k.startswith("us_timer_")
            if k[len("us_timer_"):] in l:
                return name, score
        return categorizer

    categorizers.append(prefix_categorizer("us_timer_slowpath_", "slowpaths", 20))
    categorizers.append(prefix_categorizer("us_timer_slowpath_", "avoidable runtime overhead", 10))
    categorizers.append(prefix_categorizer("us_timer_slot_", "api conversion", 20))
    categorizers.append(prefix_categorizer("us_timer_slot_", "avoidable runtime overhead", 10))
    categorizers.append(prefix_categorizer("us_timer_wrap_", "api conversion", 20))
    categorizers.append(prefix_categorizer("us_timer_wrap_", "avoidable runtime overhead", 10))
    categorizers.append(list_categorizer(["compileFunction"], "llvm+irgen", 20))
    categorizers.append(list_categorizer(["compileFunction"], "tiering overhead", 10))
    categorizers.append(list_categorizer(["in_interpreter", "main_toplevel"], "in interpreter", 20))
    categorizers.append(list_categorizer(["in_interpreter", "main_toplevel"], "tiering overhead", 10))
    categorizers.append(list_categorizer(["in_jitted_code", "in_builtins", "in_baseline_jitted_code"], "things that should be fast", 10))
    categorizers.append(list_categorizer(["rewriter", "createrewriter"], "rewriter", 20))
    categorizers.append(list_categorizer(["rewriter", "createrewriter"], "tiering overhead", 10))
    categorizers.append(list_categorizer(["typeNew"], "things that should be fast", 10))
    categorizers.append(list_categorizer(["unwinding", "getTopPythonFrame"], "unwinding", 10))
    # categorizers.append(list_categorizer(["unwinding", "getTopPythonFrame", "gc_collection"], "using modern techniques", 60))
    categorizers.append(list_categorizer(["caching_parse_file", "cpyton_parsing"], "parsing", 20))
    categorizers.append(list_categorizer(["gc_collection"], "gc collection", 10))

    categorize_at = [20, 10]
    # categorizers.append(lambda k: (k, 1)) # for debugging

    stat_names = set()
    for b in BENCHMARKS:
        for stat_name in allstats[b]:
            if not stat_name.startswith("us_timer_"):
                continue
            stat_names.add(stat_name)

    for max_specificity in categorize_at:
        print
        # print max_specificity

        results = {b:{} for b in BENCHMARKS}
        for sn in stat_names:
            category = "misc"
            specificity = 0

            for categorizer in categorizers:
                r = categorizer(sn)
                if r is None:
                    continue
                if r[1] > max_specificity:
                    continue
                if r[1] == specificity:
                    print "Ambiguous specificity between %r and %r when applied to %r" % (category, r[0], sn)
                if r[1] > specificity:
                    specificity = r[1]
                    category = r[0]

            for b in BENCHMARKS:
                results[b][category] = results[b].get(category, 0) + int(allstats[b].get(sn, 0))

        cutoff = 10 # in ms
        for k in results[BENCHMARKS[0]].keys():
            if k == "misc":
                continue

            if sum(results[b][k] for b in BENCHMARKS) < cutoff * 1000 * len(BENCHMARKS):
                for b in BENCHMARKS:
                    results[b]["misc"] = results[b].get("misc", 0) + results[b][k]
                    del results[b][k]

        results = [(k, [results[b][k] for b in BENCHMARKS]) for k in results[BENCHMARKS[0]].keys()]
        def sort_key((k, l)):
            if k == "misc":
                return -1
            return sum(l) # should be product
        results.sort(key=sort_key, reverse=True)

        print "%30s" % '',
        for b in BENCHMARKS:
            print "% 25s" % b[:-3],
        print "% 15s" % "(geomean)",
        print
        for (k, l) in results:

            # if k.startswith('us_timer_'):
                # k = k[len('us_timer_'):]

            print "%30s" % k,
            cpython_product = 1.0
            for i, r in enumerate(l):
                cpython_percent = r/10/CPYTHON_TIMES[BENCHMARKS[i]]
                cpython_product *= cpython_percent
                s = "%d (% 3s%%)" % (r/1000, cpython_percent)
                print "% 25s" % s,

            cpython_product **= (1.0 / len(l))
            print "%14.0f%%" % cpython_product,
            print
