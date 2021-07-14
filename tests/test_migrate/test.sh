#!/bin/sh
PROJ=test_migrate
SETTINGS=--settings=tests.$PROJ.settings

# test for Issue 190
#   "Best way to run in environments without connectivity to Salesforce API? #190"

# Test with two "sqlite3" databases and SalesforceModels
# Verify that tables with SalesforceModels
# - are created in "salesforce" database and
# - not created in "default" database
# The default SalesforceRouter must be used.

python manage.py makemigrations $SETTINGS $PROJ &&
python manage.py test $SETTINGS tests.$PROJ &&
python manage.py migrate $SETTINGS --verbosity=0 &&
python manage.py migrate $SETTINGS --database=salesforce --verbosity=0 &&
echo .tables | sqlite3 db_tmp_salesforce | grep -w Lead &&
echo .tables | sqlite3 db_tmp_salesforce | grep -w Contact
ret=$?

echo .tables | sqlite3 db_tmp_default | grep -w Contact
ret2=$?

# delete explicit names to see a warning if they don't exist
rm db_tmp_default
rm db_tmp_salesforce
rm tests/$PROJ/migrations/0001_initial.py
ret3=$?
rm -rf tests/$PROJ/migrations/

test $ret -eq 0 -a $ret2 -eq 1 -a $ret3 -eq 0
ret=$?

if test $ret -ne 0; then
    echo "Test failed"
    false
fi
