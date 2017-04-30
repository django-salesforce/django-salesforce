#!/bin/bash
# expects that "tox" has been run
.tox/py36-dj111/bin/coverage run --source salesforce manage.py check >/dev/null
for x in py27-dj18 py34-dj19 py35-dj110 py36-dj111; do
    .tox/${x}/bin/coverage run -a --source salesforce manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a --source salesforce manage.py test salesforce
done
COVERAGE=.tox/py36-dj111/bin/coverage
for x in $(ls -d tests/test_* | sed "s%/%.%"); do
    $COVERAGE run -a --source salesforce manage.py test --settings=$x.settings $x
done
$COVERAGE html
$COVERAGE report
