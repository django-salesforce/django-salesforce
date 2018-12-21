#!/bin/sh
python manage.py test --settings=tests.test_compatibility.settings tests.test_compatibility
