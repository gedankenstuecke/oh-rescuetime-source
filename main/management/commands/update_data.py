from django.core.management.base import BaseCommand
from main.models import DataSourceMember
from datauploader.tasks import process_rescuetime
import arrow
from datetime import timedelta


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = DataSourceMember.objects.all()
        for rescuetime_user in users:
            if rescuetime_user.last_updated < (arrow.now() - timedelta(days=4)):
                oh_id = rescuetime_user.user.oh_id
                process_rescuetime.delay(oh_id)
            else:
                print("didn't update {}".format(rescuetime_user.user.oh_id))
