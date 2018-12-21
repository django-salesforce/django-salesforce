#!/bin/sh
python manage.py test --settings=tests.test_dynamic_auth.settings tests.test_dynamic_auth
