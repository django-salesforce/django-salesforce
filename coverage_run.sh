#!/bin/bash
# it expects that "tox" has been run recently for a current tox.ini configuration
COVERAGE=.tox/dj40-py310/bin/coverage
export COVERAGE_FILE=.coverage_main
SOURCE="--source=salesforce"
$COVERAGE run $SOURCE manage.py check >/dev/null
$COVERAGE run -a $SOURCE manage.py inspectdb --database=salesforce Account >/dev/null
$COVERAGE run -a $SOURCE manage.py inspectdb --database=salesforce --table-filter=Account >/dev/null
$COVERAGE run -a $SOURCE manage.py inspectdb --database=salesforce --tooling-api >/dev/null
$COVERAGE run -a $SOURCE manage.py makemigrations
$COVERAGE run -a $SOURCE manage.py migrate --database=default
$COVERAGE run -a $SOURCE manage.py check --settings=tests.tooling.settings

for x in dj21-py38 dj22-py38 dj31-py39 dj40-py310 dj50-py312; do
    echo "*** $x ***"
    .tox/${x}/bin/coverage run -a $SOURCE manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a $SOURCE manage.py test salesforce
done
for DIR in tests/test_* tests/no_salesforce tests/t_debug_toolbar tests/no_django_dbapi; do
    x=${DIR//\//.}
    TESTS=$(find $DIR -name \*test\*.py)
    SOURCE="--source=$(echo salesforce $TESTS | sed 's/\.py\>//g; s/ /,/g; s/\//./g')"
    COVERAGE_FILE=$DIR/.coverage
    echo "*** $x ***"
    if [[ $DIR == tests/no_django_dbapi ]]; then
        # here is intentionally no "-a" because every run has a new output file
        echo DJANGO_SETTINGS_MODULE=$x.settings .tox/no_django-py38/bin/coverage run $SOURCE -m unittest discover $x
        DJANGO_SETTINGS_MODULE=$x.settings      .tox/no_django-py38/bin/coverage run $SOURCE -m unittest discover $x
    elif [[ $DIR == tests/t_debug_toolbar ]]; then
        echo .tox/debug_toolbar/bin/coverage run $SOURCE manage.py test --settings=$x.settings $x
        .tox/debug_toolbar/bin/coverage      run $SOURCE manage.py test --settings=$x.settings $x
    else
        if [[ $DIR == tests/test_mock* ]]; then
            SOURCE=$SOURCE,tests.test_mock.mocksf
        fi
        echo $COVERAGE run $SOURCE manage.py test --settings=$x.settings $x
        $COVERAGE      run $SOURCE manage.py test --settings=$x.settings $x
    fi
done
unset COVERAGE_FILE   # this is important to not overwrite the last output file
$COVERAGE combine --keep .coverage_main tests/*/.coverage
$COVERAGE html
$COVERAGE report
