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

function nextrev {
# Only look at the first parent, using that as the official sequence:
git rev-parse $1~
}

while true; do
    if grep -q "$CUR" $BENCHMARKING_DIR/bad_revs.txt; then
        echo "Skipping $CUR"
    else
        echo "Testing $CUR"

        if [ -n "$(git status --porcelain --untracked=no)" ]; then
            echo "Dirty working tree detected!"
            exit 1
        fi

        git checkout $CUR

        if git merge-base --is-ancestor HEAD 069d309; then
            git cherry-pick --no-commit 4c7b796
        fi

        make clean
        make pyston_release || make pyston_release
        python $BENCHMARKING_DIR/measure_perf.py --submit --save-by-commit --skip-repeated --allow-dirty

        git reset --hard
    fi

    CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)

    if [ -z "$CUR" ]; then
        break
    fi
done
