import unittest
from salesforce.backend.test_helpers import current_user
from tests.tooling.models import (
    # CustomObject, CustomField,
    EntityDefinition, FieldDefinition,
    UserEntityAccess, UserFieldAccess,
    # PermissionDependency,
    # PermissionSet, PermissionSetGroup, PermissionSetGroupComponent,
    User,
)


class PermissionTest(unittest.TestCase):
    def test_permissions_by_tooling(self):
        # "When retrieving results with Metadata or FullName fields, the query
        #  qualificatio​ns must specify no more than one row for retrieval."
        entity_definitions = EntityDefinition.objects.defer('full_name', 'metadata')
        entity_definition = EntityDefinition.objects.get(qualified_api_name='Contact')
        assert entity_definitions

        field_definitions = FieldDefinition.objects.filter(qualified_api_name='Contact').defer('full_name', 'metadata')
        field_definitions = (FieldDefinition.objects.filter(entity_definition_id=entity_definition.durable_id)
                             .defer('full_name', 'metadata'))
        field_definition = FieldDefinition.objects.get(entity_definition_id='Contact', qualified_api_name='Email')
        assert field_definitions

        current_user_id = User.objects.get(username=current_user).pk

        user_entity_access = UserEntityAccess.objects.get(durable_id='%s.%s' %
                                                          (entity_definition.durable_id, current_user_id))
        user_field_access = UserFieldAccess.objects.get(durable_id='%s.%s' %
                                                        (field_definition.durable_id, current_user_id))

        x = user_entity_access
        assert [x.is_editable, x.is_readable] == [True, True]

        x = user_field_access
        assert [x.is_accessible, x.is_creatable, x.is_updatable] == [True, True, True]
