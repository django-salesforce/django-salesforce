#!/bin/bash

# TODO check also sometimes manually that a file "models.py"
#      created by older Python, Django and django-salesferce versions
#      can be imported by newer versions.
#      test it by command
#      .tox/dj..-py.../bin/python manage.py check --settings=tests.inspectdb.settings --traceback
#      after version switching


echo "python manage.py inspectdb --database=salesforce --concise-db-column >tests/inspectdb/models.py"
python manage.py inspectdb --database=salesforce --concise-db-column --traceback >tests/inspectdb/models.py
RESULT_0=$?
if [ $RESULT_0 == 0 ]; then

    echo "*** check"
    python manage.py check --settings=tests.inspectdb.settings --traceback
    RESULT_1=$?

    echo "*** slow_test"
    python tests/inspectdb/slow_test.py
    RESULT_2=$?


    echo "*** parse test ***"
    # parse tests don't import tthe models.py
    DJANGO_SETTINGS_MODULE=salesforce.testrunner.settings python -m unittest tests.inspectdb.tests
    #python manage.py test --settings=tests.inspectdb.settings tests.inspectdb
    RESULT_3=$?

    echo "*** dependent dynamic model test ***"
    sed 's/import models$/import models_template as models/' tests/inspectdb/models.py \
        >tests/inspectdb/dependent_model/models_template.py
    DJANGO_SETTINGS_MODULE=tests.inspectdb.dependent_model.settings python manage.py check
    RESULT_4=$?
    DJANGO_SETTINGS_MODULE=tests.inspectdb.dependent_model.settings python -m unittest tests.inspectdb.dependent_model.test
    #python manage.py test --settings=tests.inspectdb.settings tests.inspectdb
    RESULT_5=$?

    echo -en "\nSummary: "
    if [ $RESULT_1 == 0 -a $RESULT_2 == 0 -a $RESULT_3 == 0 -a $RESULT_4 == 0 -a $RESULT_5 == 0 ]; then
        echo OK
    else
        echo ERROR
        false
    fi
else
    false
fi
