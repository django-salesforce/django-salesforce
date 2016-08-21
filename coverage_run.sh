#!/bin/bash
# expects that "tox" has been run
.tox/py35-dj110/bin/coverage run --source salesforce manage.py validate >/dev/null
for x in py34-dj18 py27-dj19 py35-dj110; do
    .tox/${x}/bin/coverage run -a --source salesforce manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a --source salesforce manage.py test salesforce
done
COVERAGE=.tox/py35-dj110/bin/coverage
for x in $(ls -d tests/test_* | sed "s%/%.%"); do
    $COVERAGE run -a --source salesforce manage.py test --settings=$x.settings $x
done
$COVERAGE html
$COVERAGE report
