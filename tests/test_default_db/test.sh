#!/bin/sh
python manage.py test --settings=tests.test_default_db.settings tests.test_default_db
