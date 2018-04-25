from django.test import TestCase
from freezegun import freeze_time
from django.conf import settings
from django.core.management import call_command
import vcr
from open_humans.models import OpenHumansMember
from main.models import DataSourceMember


class ManagementTestCase(TestCase):
    """
    test that files are parsed correctly
    """

    def setUp(self):
        settings.OPENHUMANS_CLIENT_ID = 'oh_client_id'
        settings.OPENHUMANS_CLIENT_SECRET = 'oh_client_secret'
        settings.MOVES_CLIENT_ID = 'moves_client_id'
        settings.MOVES_CLIENT_SECRET = 'moves_client_secret'

    @freeze_time('2016-06-24')
    @vcr.use_cassette('main/tests/fixtures/import_users.yaml',
                      record_mode='none')
    def test_import_command(self):
        self.assertEqual(len(OpenHumansMember.objects.all()),
                         0)
        self.assertEqual(len(DataSourceMember.objects.all()),
                         0)
        call_command('import_users',
                     infile='main/tests/fixtures/import_list.txt',
                     delimiter=',')
        self.assertEqual(len(OpenHumansMember.objects.all()),
                         1)
        self.assertEqual(len(DataSourceMember.objects.all()),
                         1)
