#!/bin/sh
PROJ=z_test_issue_160
SETTINGS=--settings=tests.$PROJ.settings

python manage.py makemigrations $SETTINGS &&
python manage.py test $SETTINGS tests.$PROJ &&
python manage.py migrate $SETTINGS --verbosity=0 &&
python manage.py migrate $SETTINGS --database=salesforce --verbosity=0 &&
echo .tables | sqlite3 db_tmp_salesforce | grep -w Lead &&
echo .tables | sqlite3 db_tmp_salesforce | grep -w Contact
ret=$?
echo .tables | sqlite3 db_tmp_default | grep -w Contact
ret2=$?
test $ret -eq 0 -a $ret2 -eq 1
ret=$?
rm db_tmp_default
rm db_tmp_salesforce
rm tests/$PROJ/migrations/0001_initial.py
test
if test $ret -ne 0; then
    echo "Test faied"
fi
test $ret -eq 0
