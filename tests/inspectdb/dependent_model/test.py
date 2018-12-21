import unittest
import django
# in ortder to can run also by unittest without manage.py
django.setup()
from tests.inspectdb.dependent_model.models import Organization  # NOQA must be after setup()


class DependentModelTest(unittest.TestCase):
    def test_dependent_model_can_copy_fields(self):
        self.assertIn('@', Organization.objects.get().created_by.Username)
        Organization.objects.get().address


if __name__ == '__main__':
    unittest.main()
