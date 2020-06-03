#!/bin/bash
if [[ "$SLOW_TESTS" = "on" ]]; then
    MORE_TESTS="tests/inspectdb tests/tooling"
fi
RET=0
for x in tests/test_* $MORE_TESTS; do
    if test -e $x/test.sh; then
        echo
        echo "== $x =="
        $x/test.sh || RET=$?
    fi
done
test $RET -eq 0
