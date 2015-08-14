#!/bin/bash
RET=0
for x in tests/test_*; do
    if test -e $x/test.sh; then
        echo
        echo "== $x =="
        $x/test.sh || RET=$?
    fi
done
test $RET -eq 0
