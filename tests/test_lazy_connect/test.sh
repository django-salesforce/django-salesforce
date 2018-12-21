#!/bin/sh
python manage.py test --settings=tests.test_lazy_connect.settings tests.test_lazy_connect
