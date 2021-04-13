#!/bin/sh
python manage.py test --settings=tests.test_mock2.settings tests.test_mock2.test_rec
