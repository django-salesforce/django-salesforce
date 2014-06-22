#!/bin/bash
# expects that "tox" has been run
.tox/py27dj17/bin/coverage run --source salesforce manage.py validate >/dev/null
for x in py26dj14 py27dj17 py33dj15 py34dj16; do
    .tox/${x}/bin/coverage run -a --source salesforce manage.py inspectdb --database=salesforce >/dev/null
    .tox/${x}/bin/coverage run -a --source salesforce manage.py test salesforce
done
coverage html
coverage report
