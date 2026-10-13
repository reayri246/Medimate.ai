from pathlib import Path
from tempfile import TemporaryDirectory

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction


SOURCE_ALIAS = 'sqlite_source'
EXCLUDED_APPS = {'contenttypes', 'sessions'}


class Command(BaseCommand):
    help = 'Copy records from a SQLite database into an empty PostgreSQL database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            default='db.sqlite3',
            help='Path to the SQLite database file (default: db.sqlite3).',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirm importing the source records into PostgreSQL.',
        )

    def handle(self, *args, **options):
        target = connections['default']
        source_path = Path(options['source']).resolve()
        if target.vendor != 'postgresql':
            raise CommandError('The target database must be PostgreSQL.')
        if not source_path.is_file():
            raise CommandError(f'SQLite source database does not exist: {source_path}')
        if not options['yes']:
            raise CommandError(
                'Import not started. Back up both databases, then rerun with --yes.'
            )
        if SOURCE_ALIAS in connections.databases:
            raise CommandError(f'The database alias {SOURCE_ALIAS!r} is already configured.')

        connections.databases[SOURCE_ALIAS] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(source_path),
        }
        try:
            source = connections[SOURCE_ALIAS]
            with source.cursor() as cursor:
                tables = set(source.introspection.table_names(cursor))
            if 'django_migrations' not in tables:
                raise CommandError(
                    'The source is not a migrated Django database (django_migrations is missing).'
                )

            import_models = [
                model for model in apps.get_models()
                if model._meta.app_label not in EXCLUDED_APPS
                and not (
                    model._meta.app_label == 'auth'
                    and model._meta.model_name == 'permission'
                )
            ]
            populated_models = [
                model._meta.label
                for model in import_models
                if model._base_manager.using('default').exists()
            ]
            if populated_models:
                raise CommandError(
                    'The PostgreSQL database already contains application data '
                    f'({", ".join(populated_models[:5])}). Import only into a fresh database.'
                )

            with TemporaryDirectory(prefix='medimate-sqlite-import-') as temp_dir:
                fixture_path = Path(temp_dir) / 'sqlite-data.json'
                call_command(
                    'dumpdata',
                    database=SOURCE_ALIAS,
                    natural_foreign=True,
                    natural_primary=True,
                    exclude=['contenttypes', 'auth.permission', 'sessions'],
                    output=str(fixture_path),
                    verbosity=0,
                )
                with transaction.atomic(using='default'):
                    call_command(
                        'loaddata',
                        str(fixture_path),
                        database='default',
                        verbosity=1,
                    )
        finally:
            if SOURCE_ALIAS in connections.databases:
                connections[SOURCE_ALIAS].close()
                del connections.databases[SOURCE_ALIAS]

        self.stdout.write(self.style.SUCCESS(
            'SQLite records imported. Copy the referenced media files separately.'
        ))
