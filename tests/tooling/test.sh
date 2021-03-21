#!/bin/bash
echo "python manage.py inspectdb --database=salesforce --tooling-api >tests/tooling/models.py"
python manage.py inspectdb --database=salesforce --tooling-api --traceback >tests/tooling/models.py
RESULT_0=$?
if [ $RESULT_0 == 0 ]; then

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
else
    false
fi
