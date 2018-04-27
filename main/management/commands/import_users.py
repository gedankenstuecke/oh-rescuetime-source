from django.core.management.base import BaseCommand
from open_humans.models import OpenHumansMember
from main.models import DataSourceMember
from django.conf import settings
from datauploader.tasks import process_moves
# import vcr


class Command(BaseCommand):
    help = 'Import existing users from legacy project'

    def add_arguments(self, parser):
        parser.add_argument('--infile', type=str,
                            help='CSV with project_member_id & refresh_token')
        parser.add_argument('--delimiter', type=str,
                            help='CSV delimiter')

    # @vcr.use_cassette('import_users.yaml', decode_compressed_response=True)
    #                  record_mode='none')
    def handle(self, *args, **options):
        for line in open(options['infile']):
            line = line.strip().split(options['delimiter'])
            oh_id = line[0]
            oh_refresh_token = line[1]
            moves_refresh_token = line[2]
            if len(OpenHumansMember.objects.filter(
                     oh_id=oh_id)) == 0:
                oh_member = OpenHumansMember.create(
                                    oh_id=oh_id,
                                    access_token="mock",
                                    refresh_token=oh_refresh_token,
                                    expires_in=-3600)
                oh_member._refresh_tokens(settings.OPENHUMANS_CLIENT_ID,
                                          settings.OPENHUMANS_CLIENT_SECRET)
                moves_member = DataSourceMember(
                    access_token="mock",
                    refresh_token=moves_refresh_token,
                    token_expires=DataSourceMember.get_expiration(
                        -3600)
                )
                moves_member.user = oh_member
                moves_member._refresh_tokens(
                    client_id=settings.MOVES_CLIENT_ID,
                    client_secret=settings.MOVES_CLIENT_SECRET
                )
                moves_member.save()
                process_moves.delay(oh_member.oh_id)
                # process_moves(oh_member.oh_id)
