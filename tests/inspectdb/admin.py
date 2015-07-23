from __future__ import absolute_import
from . import models
from salesforce.testrunner.example.universal_admin import register_omitted_classes

register_omitted_classes(models)
