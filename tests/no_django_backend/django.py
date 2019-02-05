"""Fake Django is for running some low level tests also without Django.

It is the easiest way how to verify that some code does not depend on a Django version.
"""
import warnings

VERSION = (2, 1, 'mock')

warnings.warn("Fake Django is for running some tests without Django.")


class Settings(object):
    pass


mock_sf_settings = Settings()
