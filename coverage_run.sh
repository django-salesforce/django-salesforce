#!/bin/bash
# it expects that "tox" has been run recently for a current tox.ini configuration
COVERAGE=.tox/py310-dj32/bin/coverage
SOURCE="--source salesforce,$(echo tests/*/*test*.py | sed 's/ /,/g')"
$COVERAGE run $SOURCE manage.py check >/dev/null
for x in py35-dj20 py36-dj21 py38-dj30 py310-dj32; do
    echo "*** $x ***"
    .tox/${x}/bin/coverage run -a $SOURCE manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a $SOURCE manage.py test salesforce
done
for x in $(ls -d tests/test_* tests/no_django | sed "s%/%.%"); do
    echo "*** $x ***"
    $COVERAGE run -a $SOURCE manage.py test --settings=$x.settings $x
done
$COVERAGE html
$COVERAGE report
