from django.core.management.commands.migrate import Command as MigrateCommand  # type: ignore[import]
from django.db import connections


class Command(MigrateCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--batch', action='store_true',
            help='Run more commands together.',
        )

    def handle(self, *args, **options):
        database = options['database']
        connection = connections[database]
        if connection.vendor == 'salesforce':
            connection.migrate_options = {'batch', options.batch}
        super().handle(*args, **options)
