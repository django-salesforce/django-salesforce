#!/bin/bash
if python manage.py inspectdb --database=salesforce --traceback >tests/inspectdb/models.py; then

	# Run both tests even if the first test fails. With old Django versions can
	# the read/write test pass (useful information) though validation failed.

	echo "*** validate"
	python manage.py validate --settings=tests.inspectdb.settings --traceback
	RESULT_1=$?

	echo "*** slow_test"
	python tests/inspectdb/slow_test.py
	RESULT_2=$?

	echo "*** parse test ***"
	DJANGO_SETTINGS_MODULE=salesforce.testrunner.settings python -m unittest tests.inspectdb.tests
	#python manage.py test --settings=tests.inspectdb.settings tests.inspectdb
	RESULT_3=$?

	if [ $RESULT_1 == 0 -a $RESULT_2 == 0 -a $RESULT_3 == 0 ]; then
		echo OK
	else
		echo ERROR
		false
	fi
fi
