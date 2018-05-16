from django.core.management.base import BaseCommand
from main.models import DataSourceMember
from datauploader.tasks import process_rescuetime
import arrow
from datetime import timedelta


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = DataSourceMember.objects.all()
        for moves_user in users:
            if moves_user.last_updated < (arrow.now() - timedelta(days=4)):
                oh_id = moves_user.user.oh_id
                process_rescuetime.delay(oh_id)
            else:
                print("didn't update {}".format(moves_user.moves_id))
