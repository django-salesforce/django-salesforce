#!/bin/sh
DJANGO_VER=$(python -c "import django; print(django.get_version())")
if ! [ $DJANGO_VER '<' 1.6 ]; then
	TEST_BASE=tests.
fi
python manage.py test --settings=tests.test_compatibility.settings ${TEST_BASE}test_compatibility
