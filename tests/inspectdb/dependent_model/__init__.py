from django.apps import AppConfig


class AutoModelConf(AppConfig):
    name = 'tests.inspectdb'
    label = 'auto_model'


class DependentModelConf(AppConfig):
    name = 'tests.inspectdb.dependent_model'
    label = 'dependent_model'
