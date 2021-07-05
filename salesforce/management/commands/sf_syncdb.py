import os
import re
import shutil
from typing import Any, Dict
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db.models.fields import NOT_PROVIDED
from django.template import engines
from salesforce import fields, API_VERSION

django_engine = engines['django']

SFDX_PROJECT_TEMPLATE = """{
    "packageDirectories": [
      {
        "path": "force-app",
        "default": true
      }
    ],
    "namespace": "",
    "sourceApiVersion": "{{ API_VERSION }}"
  }
"""
sfdx_project_template = django_engine.from_string(SFDX_PROJECT_TEMPLATE)

OBJECT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <deploymentStatus>Deployed</deploymentStatus>
    <label>{{ verbose_name }}</label>
    <nameField>
        <label>{{ name_field_label }}</label>
        <type>Text</type>
    </nameField>
    <pluralLabel>{{ verbose_name_plural }}</pluralLabel>
    <sharingModel>ReadWrite</sharingModel>
</CustomObject>
"""
object_template = django_engine.from_string(OBJECT_TEMPLATE)

STANDARD_FIELD_TEMPLATE = ["""
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <type>{{ type }}</type>
""", """
    <fullName>{{ column }}</fullName>
    <label>{{ verbose_name }}</label>
    <inlineHelpText>{{ help_text }}</inlineHelpText>
    <required>{{ null|yesno:"false,true" }}</required>
    <unique>{{ unique|yesno:"true,false" }}</unique>
    <defaultValue>{{ default }}</defaultValue>
</CustomField>
"""]
# unimplemented standard attributes: ["description", "externalId", "trackFeedHistory", "trackTrending"]


def make_field_template(type, extra_template='', exclude=None):
    if extra_template:
        if not extra_template.startswith('    '):
            extra_template = '    ' + extra_template
        if extra_template.endswith('\n'):
            extra_template = extra_template[:-1]
    template = (
        STANDARD_FIELD_TEMPLATE[0].replace('{{ type }}', type) +
        extra_template +
        STANDARD_FIELD_TEMPLATE[1]
    ).replace('\n\n', '\n')
    if exclude:
        template = re.sub(r'\s*<{exclude}>.*</{exclude}>\s*'.format(exclude=exclude), '', template)
    return django_engine.from_string(template)


lookup_field_template = make_field_template(
    "Lookup", """
    <referenceTo>{{ related_db_table }}</referenceTo>
    <relationshipLabel>{{ remote_related_name }}</relationshipLabel>
    <relationshipName>{{ remote_related_name }}</relationshipName>
    <deleteConstraint>{{ delete_constraint }}</deleteConstraint>
""", exclude='defaultValue')
# unimplemented attribute "relationshipLabel" replaced by "relationshipName"

char_field_template = make_field_template(
    "Text", "<length>{{ max_length }}</length>"
)
# unimplemented Text attributes: ["caseSensitive"]

picklist_field_template = make_field_template(
    "Picklist", """
    <valueSet>
        <restricted>false</restricted>
        <valueSetDefinition>
            <sorted>false</sorted>
            {% for ch_name, ch_label in choices %}
            <value>
                <fullName>{{ ch_name }}</fullName>
                <default>{% if ch_name == default %}true{% else %}false{% endif %}</default>
                <label>{{ ch_value }}</label>
            </value>
            {% endfor %}
        </valueSetDefinition>
    </valueSet>
""")
# unimplemented Picklist attributes: ["sorted", value: "isActive"]

bool_field_template = make_field_template(
    "Checkbox", exclude='required'
)

integer_field_template = make_field_template(
    "Number", "<scale>0</scale>")

decimal_field_template = make_field_template(
    "Number", """
    <precision>{{ max_digits }}</precision>
    <scale>{{ decimal_places }}</scale>
""")

float_field_template = make_field_template(
    "Number"
)

PROFILE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<Profile xmlns="http://soap.sforce.com/2006/04/metadata">
    <custom>false</custom>
{% for permission in permissions %}{{ permission }}
{% endfor %}
</Profile>
"""
profile_template = django_engine.from_string(PROFILE_TEMPLATE)

OBJECT_PERMISSION_TEMPLATE = """
    <objectPermissions>
        <object>{{ table }}</object>
        <allowCreate>true</allowCreate>
        <allowDelete>true</allowDelete>
        <allowEdit>true</allowEdit>
        <allowRead>true</allowRead>
        <modifyAllRecords>true</modifyAllRecords>
        <viewAllRecords>true</viewAllRecords>
    </objectPermissions>"""
object_permission_template = django_engine.from_string(OBJECT_PERMISSION_TEMPLATE)

FIELD_PERMISSION_TEMPLATE = """
    <fieldPermissions>
        <field>{{ table }}.{{ field.column }}</field>
        <editable>true</editable>
        <readable>true</readable>
    </fieldPermissions>"""
field_permission_template = django_engine.from_string(FIELD_PERMISSION_TEMPLATE)


class Command(BaseCommand):
    # this uses SFDX and simplified Metadata API

    help = "Sync the salesforce database for models with 'sf_managed' meta."
    base = 'force-app/main/default'
    options = None  # type: Dict[str, Any]

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(self, *args, **kwargs)
        self.permissions = []
        self.tmpdir = '/tmp/{USER}-django-salesforce'.format(USER=os.environ['USER'])

    def add_arguments(self, parser):
        parser.add_argument(
            '--to-profiles',
            help='''Users profiles to that should be assigned object permissions.
                e.g. "Standard User,Markening User".
                System Administrator profile is assigned automatically.'''
        )

        parser.add_argument(
            '--namespace', default=None,
            help="Namespace prefix of objects or fields that will be managed "
                 "if they are in a sf_managed model. "
                 "Namespace \'\' if for custom fields without a namespace. "
                 "(The user must be logged as an Administrator of the Organization with the same namespace prefix.) "
                 "Default value None is to not manage by namespace and only manage by explicit 'sf_managed'."
        )

    def handle(self, *args, **options):
        self.options = options
        if os.path.isdir(self.tmpdir):
            shutil.rmtree(self.tmpdir)
        self.add_metadata('sfdx-project.json', sfdx_project_template, {'API_VERSION': API_VERSION})
        for app_config in apps.get_app_configs():
            for model in app_config.get_models():
                if hasattr(model, '_salesforce_object'):
                    self.handle_model(model)
        profiles = ['Admin']
        if options['to_profiles']:
            profiles.extend(options['to_profiles'].split(','))
        for profile in profiles:
            profile_path = '{base}/profiles/{profile}.profile-meta.xml'.format(
                base=self.base, profile=quote_profile_name(profile)
            )
            self.add_metadata(
                path=profile_path, template=profile_template, context={'permissions': self.permissions})
        # shutil.rmtree(self.tmpdir)

    def handle_model(self, model):
        if model._meta.sf_managed:
            db_table = model._meta.db_table
            if db_table.endswith('__c') and model._meta.namespace == self.namespace:
                for field in model._meta.fields:
                    if field.column == 'Name':
                        name_field_label = field.verbose_name
                        break
                else:
                    name_field_label = '{db_table} Name'.format(db_table=db_table)
                self.add_metadata(
                    path='{base}/objects/{table}/{table}.object-meta.xml'.format(base=self.base, table=db_table),
                    template=object_template,
                    context=model._meta.__dict__,
                    context_2={'name_field_label': name_field_label, 'table': db_table},
                )
                self.permissions.append(object_permission_template.render(
                    {'table': db_table, 'name_field_label': name_field_label}))
            for field in model._meta.fields:
                if field.sf_managed is not None:
                    field_managed = field.sf_managed
                else:
                    field_managed = model._meta.sf_managed and self.options['namespace'] is not None
                    #                and get_namespace(field.column) == self.namespace
                if field_managed:
                    assert field.column.endswith('__c')
                    md_path = '{base}/objects/{table}/fields/{column}.field-meta.xml'.format(
                        base=self.base, table=db_table, column=field.column
                    )
                    context = field.__dict__.copy()

                    if isinstance(field, fields.CharField):
                        if not field.choices:
                            template = char_field_template
                            if isinstance(field.default, str):
                                translation = {ord('"'): '\\"', ord('\\'): '\\\\'}
                                context['default'] = '"{}"'.format(field.default.translate(translation))
                            elif field.default is NOT_PROVIDED:
                                context['default'] = ''
                            else:
                                raise NotImplementedError  # None
                        else:
                            template = picklist_field_template
                    elif isinstance(field, fields.BooleanField):
                        template = bool_field_template
                    elif isinstance(field, fields.IntegerField):
                        template = integer_field_template
                    elif isinstance(field, fields.DecimalField):
                        template = decimal_field_template
                    elif isinstance(field, fields.FloatField):
                        template = float_field_template
                    elif isinstance(field, fields.ForeignKey):
                        template = lookup_field_template
                        context['related_db_table'] = field.related_model._meta.db_table
                        context['remote_related_name'] = field.remote_field.get_accessor_name()
                        context['delete_constraint'] = (
                            'Restrict' if field.remote_field.on_delete is fields.PROTECT else 'SetNull'
                        )
                    else:
                        raise NotImplementedError

                    self.add_metadata(md_path, template, context=context)
                    if field.null:
                        self.permissions.append(field_permission_template.render(
                            {'table': db_table, 'field': field}))

    def add_metadata(self, path, template, context, context_2=None):
        if context_2:
            context = context.copy()
            context.update(context_2)
        if self.options['verbosity'] >= 2:
            print('METADATA', path)
            print(template.render(context))
        full_path = os.path.join(self.tmpdir, path)
        if not os.path.isdir(os.path.dirname(full_path)):
            os.makedirs(os.path.dirname(full_path), mode=0o700)
        with open(full_path, 'w') as f:
            f.write(template.render(context))


def quote_profile_name(name):
    pos = 0
    out = []
    for match in re.finditer(r'[^- \w]', name):
        out.append(name[pos:match.start()] + '%{:02X}'.format(ord(match.group()).upper()))
        pos = match.end()
    out.append(name[pos:])
    return ''.join(out)
