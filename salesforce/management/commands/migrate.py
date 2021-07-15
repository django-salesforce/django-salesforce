from django.core.management.commands.migrate import Command as MigrateCommand  # type: ignore[import]
from django.db import connections


class Command(MigrateCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        # parser.add_argument(
        #     '--batch', action='store_true',
        #     help='Run more commands together.',
        # )
        parser.add_argument(
            '--sf-interactive', action='store_true',
            help='Run migrate subcommands interactive.',
        )
        parser.add_argument(
            '--sf-no-check-permissions', action='store_true',
            help='Run migrate without check permissions of CustomObjects.',
        )
        parser.add_argument(
            '--sf-create-permission-set', action='store_true',
            help='only Create PermissionSet "Django_Salesforce" on a new SF database to enable migrations.',
        )
        parser.add_argument(
            '--sf-debug-info', action='store_true',
            help='Print a short context info before raising some exceptions.',
        )

    def handle(self, *args, **options):
        database = options['database']
        connection = connections[database]
        if connection.vendor == 'salesforce':
            connection.migrate_options = {
                # 'batch': options['batch'],
                'sf_debug_info': options['sf_debug_info'],
                'sf_interactive': options['sf_interactive'],
                'sf_no_check_permissions': options['sf_no_check_permissions'],
                'sf_noinput': not options['interactive'],
            }
        if options['sf_create_permission_set']:
            from salesforce.backend.schema import DatabaseSchemaEditor
            DatabaseSchemaEditor.create_permission_set(connection)
        else:
            super().handle(*args, **options)
