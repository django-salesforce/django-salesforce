#!/bin/sh
DJANGO_VER=$(python -c "import django; print(django.get_version())")
if ! [ $DJANGO_VER '<' 1.6 ]; then
	TEST_BASE=tests.
fi
python manage.py test --settings=tests.test_lazy_connect.settings ${TEST_BASE}test_lazy_connect
