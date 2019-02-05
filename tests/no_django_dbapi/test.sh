#!/bin/sh
DJANGO_SETTINGS_MODULE=tests.no_django_dbapi.settings python -m unittest discover tests/no_django_dbapi
