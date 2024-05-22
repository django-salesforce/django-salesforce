from base64 import b64encode
from typing import Optional

import django
from django.test import TestCase
from salesforce.backend.test_helpers import current_user
from salesforce.models import SalesforceModel
from salesforce.testrunner.example.models import Contact, ContentDocumentLink, ContentVersion, ContentDocument, User


def create_content_document_link(original_filename: str, attachment_body: bytes,
                                 related_object: SalesforceModel, owner_id: Optional[str] = None
                                 ) -> ContentDocumentLink:
    if owner_id is None:
        owner_id = User.objects.get(Username=current_user).pk
    blob = b64encode(attachment_body).decode('ascii')
    c_version = ContentVersion.objects.create(
        content_location='S',  # document is where: S: in Salesforce, E: outside of Salesforce, L: on a Social Netork
        path_on_client=original_filename,
        origin='C',            # C: Content Origin, H: Chatter Origin
        title=original_filename,
        version_data=blob,
        owner_id=owner_id,
    )
    c_version = ContentVersion.objects.get(pk=c_version.pk)  # refresh fields after creation
    c_doc_link = ContentDocumentLink.objects.create(
        content_document=c_version.content_document,
        linked_entity_id=related_object.pk,
        share_type='V',         # V - Viewer permission. C - Collaborator permission. I - Inferred permission
        visibility='AllUsers',  # AllUsers, InternalUsers, SharedUsers
    )
    return c_doc_link


class Test(TestCase):
    databases = {'salesforce'}

    def test_content_version(self) -> None:
        c_docs = ContentDocument.objects.filter(title='some file.txt')
        c_doc_links = list(ContentDocumentLink.objects.filter(content_document__in=c_docs))
        if c_docs and not c_doc_links:
            for x in c_docs:
                x.delete()
        if not c_doc_links:
            contact = Contact.objects.all()[0]
            c_doc_links = [create_content_document_link('some file.txt', b'abc\n', contact)]

        connection = django.db.connections['salesforce'].connection
        rel_url = c_doc_links[0].content_document.latest_published_version.version_data
        ret = connection.handle_api_exceptions('GET', rel_url)
        self.assertEqual(ret.status_code, 200)
        self.assertEqual(ret.content, b'abc\n')
