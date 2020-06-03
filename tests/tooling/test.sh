#!/bin/bash
echo "python manage.py inspectdb --database=salesforce --tooling-api >tests/tooling/models.py"
if python manage.py inspectdb --database=salesforce --tooling-api --traceback >tests/tooling/models.py; then

    # Run both tests even if the first test fails. With old Django versions can
    # the read/write test pass (useful information) though validation failed.

    echo "*** test"
    python manage.py test --settings=tests.tooling.settings tests.tooling.tests
    RESULT_1=$?

    echo "*** slow_test"
    python tests/tooling/slow_test.py
    RESULT_2=$?

    echo -en "\nSummary: "
    if [ $RESULT_1 == 0 -a $RESULT_2 == 0 ]; then
        echo OK
    else
        echo ERROR
        false
    fi
fi
