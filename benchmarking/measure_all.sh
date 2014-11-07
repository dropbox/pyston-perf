set -eu

BENCHMARKING_DIR=$PWD/$(dirname $0)

cd ../../pyston/src

CUR=$(git rev-parse HEAD)

function nextrev {
git log master --format=oneline | awk '
BEGIN {
found=0;
}

{
if (found) {
    print $1;
    exit;
}
if ($1 == "'$1'") {
    found = 1;
}
}'
}

while true; do
    echo "Testing $CUR"

    if [ -n "$(git status --porcelain --untracked=no)" ]; then
        echo "Dirty working tree detected!"
        exit 1
    fi

    git checkout $CUR
    python $BENCHMARKING_DIR/measure_perf.py --submit

    CUR=$(nextrev $CUR)
    if [ -z "$CUR" ]; then
        break
    fi
done
