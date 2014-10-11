#!/bin/sh
RET=0
for x in tests/test_*; do
    echo
    echo "== $x =="
    $x/test.sh || RET=$?
done
test $RET == 0
