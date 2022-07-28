#!/bin/bash
if test -z "$TOX_ENV_DIR"; then
    echo -e "ERROR must be run from tox\n"
fi
MYPY=$TOX_ENV_DIR/bin/mypy
$MYPY --strict salesforce/*.py
RET=$?
MORE_TESTS=tests/inspectdb
DIRS=
for x in tests/test_* $MORE_TESTS; do
    if test -e $x/test.sh; then
        if test -e $x/mypy.ini; then
            CONFIG=$x/mypy.ini
            echo "== .$MYPY --config-file=$CONFIG $x $@ =="
            $MYPY --config-file=$CONFIG $x $@ || RET=$?
        else
            DIRS="$DIRS $x"
        fi
    fi
done
CONFIG=mypy.ini
echo "== $MYPY --config-file=$CONFIG $DIRS $@ =="
$MYPY --config-file=$CONFIG $DIRS  $@ || RET=$?
test $RET -eq 0
