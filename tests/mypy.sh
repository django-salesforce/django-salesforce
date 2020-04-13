#!/bin/bash
RET=0
MORE_TESTS=tests/inspectdb
for x in tests/test_* $MORE_TESTS; do
    if test -e $x/test.sh; then
        if test -e $x/mypy.ini; then
            CONFIG=$x/mypy.ini
        else
            CONFIG=mypy.ini
        fi
	echo "== .tox/typing/bin/mypy --config-file=$CONFIG $x $@ =="
        .tox/typing/bin/mypy --config-file=$CONFIG $x $@ || RET=$?
    fi
done
test $RET -eq 0
