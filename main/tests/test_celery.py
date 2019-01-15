from datauploader.tasks import process_rescuetime
from django.test import TestCase
from freezegun import freeze_time
from django.conf import settings
import vcr
from open_humans.models import OpenHumansMember
from main.models import DataSourceMember
import arrow


class CeleryTestCase(TestCase):
    """
    test that celery processing works
    """

    def setUp(self):
        settings.OPENHUMANS_CLIENT_ID = 'oh_client_id'
        settings.OPENHUMANS_CLIENT_SECRET = 'oh_client_secret'
        settings.RESCUETIME_CLIENT_ID = 'moves_client_id'
        settings.RESCUETIME_CLIENT_SECRET = 'moves_client_secret'
        oh_member = OpenHumansMember.create(
                            oh_id=23456789,
                            access_token="new_oh_access_token",
                            refresh_token="new_oh_refresh_token",
                            expires_in=36000)
        oh_member.save()
        moves_member = DataSourceMember(
            access_token="new_moves_access_token",
            last_updated=arrow.get('2016-06-19').format(),
            last_submitted=arrow.get('2016-06-19').format()
        )
        moves_member.user = oh_member
        moves_member.save()

    @freeze_time('2016-06-24')
    @vcr.use_cassette('main/tests/fixtures/import_users.yaml',
                      record_mode='none')
    def test_update_command(self):
        oh_member = OpenHumansMember.objects.get(oh_id=23456789)
        #process_rescuetime(oh_member.oh_id)
        moves_member = oh_member.datasourcemember
        #self.assertEqual(moves_member.last_updated, arrow.get('2016-06-24'))
