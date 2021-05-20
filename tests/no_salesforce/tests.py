"""A writable test, not specifically important what is tested"""
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase

from .models import Lead, User


class Test(TestCase):
    databases = '__all__'

    def test_lead_owner_without_default(self):
        test_user = User.objects.create(username='user', last_name='a', email='a@a.au')
        test_lead = Lead(company='sf_test lead', last_name='name')
        try:
            with self.assertRaises(IntegrityError) as cm, transaction.atomic():
                # can't be saved without owner
                test_lead.save()
            self.assertIn('NOT NULL constraint failed', cm.exception.args[0])

            # can be saver with owner
            test_lead.owner = test_user
            test_lead.save()
        finally:
            if test_lead.id is not None:
                test_lead.delete()
        test_user.delete()
