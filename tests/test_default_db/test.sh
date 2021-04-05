#!/bin/sh
rm -f tests/test_default_db/migrations/000*
python manage.py makemigrations --settings=tests.test_default_db.settings test_default_db
python manage.py test --settings=tests.test_default_db.settings tests.test_default_db \
	&& \
    rm tests/test_default_db/migrations/0001_initial.py && \
    rm tests/test_default_db/migrations/__init__.py
