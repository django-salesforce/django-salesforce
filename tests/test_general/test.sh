#!/bin/sh
DJANGO_SETTINGS_MODULE=tests.test_general.settings python -m unittest discover tests/test_general
