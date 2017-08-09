#!/bin/sh
PROJ=test_app_label
python manage.py test --settings=tests.$PROJ.settings tests.$PROJ
