from django.core.management.base import BaseCommand
from main.models import DataSourceMember
from datauploader.tasks import process_moves


class Command(BaseCommand):
    help = 'Updates data for all members'

    def handle(self, *args, **options):
        users = DataSourceMember.objects.all()
        for moves_user in users:
            oh_id = moves_user.user.oh_id
            process_moves.delay(oh_id)
