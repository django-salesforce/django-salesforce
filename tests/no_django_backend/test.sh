#!/bin/sh
PYTHONPATH=tests.no_django_backend \
DJANGO_SETTINGS_MODULE=tests.no_django_backend.settings python -m unittest discover tests/no_django_backend
