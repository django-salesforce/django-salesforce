#!/bin/bash
# expects that "tox" has been run
.tox/py27dj17/bin/coverage run --source salesforce --omit 'salesforce/packages/*' manage.py validate >/dev/null
for x in py26dj14 py27dj15 py33dj17 py34dj16; do
    .tox/${x}/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a --source salesforce --omit 'salesforce/packages/*' manage.py test salesforce
done
coverage html
coverage report
