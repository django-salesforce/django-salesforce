"""
Dummy module to be used if models created by `inspectdb` should be a template for a "dynamic model".

A dynamic model is an easy way to start with a simplified customized module and
to can add selected new fields from a complete current model created by
inspectdb, that we call "models template". It is even possible to frequently
refresh the template by inspectdb without confusion or rewriting the already
written customizations.

Example:
    Create a template model by
        python manage.py inspectdb --database=salesforce >your_app/models_template.py

    Replace the line "from salesforce import models"
                  by "from salesforce import models_template as models"

    That means that your `models_template` module is not considered a real
    database models module. It is an ugly file with very long lines.

Dynamic Models created by selection from


"""
from salesforce.models import *  # NOQA pylint:disable=unused-wildcard-import,wildcard-import
from salesforce.backend.indep import LazyField
import salesforce

Model = salesforce.models.ModelTemplate  # type: ignore[assignment,misc]  # noqa

# pylint: disable=invalid-name
CharField = LazyField(salesforce.models.CharField)
EmailField = LazyField(salesforce.models.EmailField)
URLField = LazyField(salesforce.models.URLField)
TextField = LazyField(salesforce.models.TextField)
IntegerField = LazyField(salesforce.models.IntegerField)
BigIntegerField = LazyField(salesforce.models.BigIntegerField)
SmallIntegerField = LazyField(salesforce.models.SmallIntegerField)
DecimalField = LazyField(salesforce.models.DecimalField)
FloatField = LazyField(salesforce.models.FloatField)
BooleanField = LazyField(salesforce.models.BooleanField)
DateTimeField = LazyField(salesforce.models.DateTimeField)
DateField = LazyField(salesforce.models.DateField)
TimeField = LazyField(salesforce.models.TimeField)
ForeignKey = LazyField(salesforce.models.ForeignKey)
OneToOneField = LazyField(salesforce.models.OneToOneField)
XJSONField = LazyField(salesforce.models.XJSONField)
AutoField = LazyField(salesforce.models.AutoField)  # not important
