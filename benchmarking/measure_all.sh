set -eu

BENCHMARKING_DIR=$PWD/$(dirname $0)

cd ../../pyston

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

function nextrev {
    C=master;
    if [ $(git rev-parse $1) = $(git rev-parse $C) ]; then
        return
    fi
    I=1;
    while true; do
        N=$(git rev-parse $C~)
        if [ "$N" = "$1" ]; then
            echo >&2 "$I more revisions to test"
            echo $C
            return
        fi
        I=$((I+1))
        C=$N
    done
}

while true; do
    if [ -e bench_env ]; then
        echo Error: $PWD/bench_env exists, please remove it
        exit 1
    fi

    if grep -q "$CUR" $BENCHMARKING_DIR/bad_revs.txt; then
        echo "Skipping $CUR"
    else
        echo "Testing $CUR"

        if [ -n "$(git status --porcelain --untracked=no --ignore-submodules)" ]; then
            echo "Dirty working tree detected!"
            exit 1
        fi

        git checkout $CUR
        git submodule update --init --recursive

        if git merge-base --is-ancestor HEAD 069d309; then
            if ! git cherry-pick --no-commit 4c7b796; then
                git reset --hard
            fi
        fi

        if git merge-base --is-ancestor HEAD c4c58d0d~; then
            if ! git cherry-pick --no-commit c4c58d0d^2; then
                git reset --hard
            fi
        fi

        if git merge-base --is-ancestor HEAD 6fc7a17~ && git merge-base --is-ancestor 5e0b10a HEAD; then
            git cherry-pick --no-commit 6fc7a17
        fi

        EXTRA_ARGS=

        if git merge-base --is-ancestor HEAD 923e960~; then
            EXTRA_ARGS="$EXTRA_ARGS --extra-jit-args=-x"
        fi

        if [ -f src/Makefile ]; then
            DIR=src
        else
            DIR=.
        fi

        make -C $DIR clean >/dev/null 2>&1 || true

        # I think we've reduced the number of times that we need to rerun cmake, but just to be
        # sure (and to support older revisions), just touch it anyway.
        touch $DIR/CMakeLists.txt

        make -C $DIR pyston_release || make -C $DIR pyston_release
        python $BENCHMARKING_DIR/measure_perf.py --submit --save-by-commit --use-previous --allow-dirty --run-pyston-interponly --pyston-executables-subdir=$DIR --run-times=3 $EXTRA_ARGS

        git reset --hard
    fi

    CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)
    # CUR=$(nextrev $CUR)

    if [ -z "$CUR" ]; then
        break
    fi

    if [ "$CUR" = "3ef50b1a2068d80ffed131d3296a8c2552a79a01" ]; then
        make -C $DIR llvm_allclean
    fi
done
