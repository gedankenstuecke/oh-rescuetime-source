from django.core.management.base import BaseCommand
from open_humans.models import OpenHumansMember
from main.models import DataSourceMember
from project_admin.models import ProjectConfiguration
from django.conf import settings
from datauploader.tasks import process_moves


class Command(BaseCommand):
    help = 'Import existing users from legacy project'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    def handle(self, *args, **options):
        client_info = ProjectConfiguration.objects.get(id=1).client_info
        for line in open(options['infile']):
            line = line.strip().split(options['delimiter'])
            oh_id = line[0]
            oh_refresh_token = line[1]
            moves_id = line[2]
            moves_refresh_token = line[3]
            if len(OpenHumansMember.objects.filter(
                     oh_id=oh_id)) == 0:
                data = {}
                data["access_token"] = "mock"
                data["refresh_token"] = oh_refresh_token
                data["expires_in"] = -3600
                oh_member = OpenHumansMember.create(oh_id, data)
                oh_member._refresh_tokens(**client_info)
                moves_member = DataSourceMember(
                    moves_id=moves_id,
                    access_token="mock",
                    refresh_token=moves_refresh_token,
                    token_expires=-3600
                )
                moves_member.user = oh_member
                moves_member.save()
                moves_member._refresh_tokens(
                    client_id=settings.MOVES_CLIENT_ID,
                    client_secret=settings.MOVES_CLIENT_SECRET
                )
                process_moves.delay(oh_member.oh_id)
