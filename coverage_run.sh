#!/bin/bash
# expects that "tox" has been run
.tox/py27dj17/bin/coverage run --source salesforce --omit 'salesforce/packages/*' manage.py validate >/dev/null
for x in py27dj14 py27dj15 py27dj17 py27dj18 py33dj17; do
    .tox/${x}/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py test salesforce
done
for x in $(ls -d tests/test_* | sed "s%/%.%"); do
    .tox/py33dj17/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py test --settings=$x.settings $x
done
.tox/py33dj17/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py test salesforce.tests.test_ssl.SslTest
coverage html
coverage report
