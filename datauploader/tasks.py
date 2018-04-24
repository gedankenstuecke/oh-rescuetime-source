"""
Asynchronous tasks that update data in Open Humans.
These tasks:
  1. delete any current files in OH if they match the planned upload filename
  2. adds a data file
"""
import logging
import json
import tempfile
import requests
import os
from celery import shared_task
from django.conf import settings
from open_humans.models import OpenHumansMember
from datetime import datetime, timedelta
from demotemplate.settings import rr
from requests_respectful import RequestsRespectfulRateLimitedError
from ohapi import api

# Set up logging.
logger = logging.getLogger(__name__)

MOVES_API_BASE = 'https://api.moves-app.com/api/1.1'
MOVES_API_STORY = MOVES_API_BASE + '/user/storyline/daily'


@shared_task
def process_moves(oh_id):
    """
    Update the moves file for a given OH user
    """
    logger.debug('Starting moves processing for {}'.format(oh_id))
    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
    moves_data = get_existing_moves(oh_access_token)
    moves_member = oh_member.datasourcemember
    moves_access_token = moves_member.get_access_token(
                            client_id=settings.MOVES_CLIENT_ID,
                            client_secret=settings.MOVES_CLIENT_SECRET)
    update_moves(oh_member, moves_access_token, moves_data)


def update_moves(oh_member, moves_access_token, moves_data):
    try:
        start_date = get_start_date(moves_data, moves_access_token)
        start_date = datetime.strptime(start_date, "%Y%m%d")
        start_date_iso = start_date.isocalendar()[:2]
        moves_data = remove_partial_data(moves_data, start_date_iso)
        stop_date_iso = (datetime.utcnow()
                         + timedelta(days=7)).isocalendar()[:2]
        while start_date_iso != stop_date_iso:
            query = MOVES_API_STORY + \
                     '/{0}-W{1}?trackPoints=true&access_token={2}'.format(
                        start_date_iso[0],
                        start_date_iso[1],
                        moves_access_token
                     )
            response = rr.get(query, realms=['moves'])
            moves_data += response.json()
            start_date = start_date + timedelta(days=7)
            start_date_iso = start_date.isocalendar()[:2]
    except RequestsRespectfulRateLimitedError:
        logger.debug(
            'requeued processing for {} with 60 secs delay'.format(
                oh_member.oh_id)
                )
        process_moves.apply_async((oh_member.oh_id), countdown=61)
    finally:
        replace_moves(oh_member)


def replace_moves(oh_member, moves_data):
    # delete old file and upload new to open humans
    tmp_directory = tempfile.mkdtemp()
    metadata = {
        'description':
        'Moves GPS maps, locations, and steps data.',
        'tags': ['GPS', 'Moves', 'steps'],
        'updated_at': str(datetime.utcnow()),
        }
    out_file = os.path.join(tmp_directory, 'moves-storyline-data.json')
    logger.debug('deleted old file for {}'.format(oh_member.oh_id))
    api.delete_file(oh_member.access_token,
                    oh_member.oh_id,
                    file_basename="moves-storyline-data.json")
    with open(out_file, 'w') as json_file:
        json.dump(moves_data, json_file)
        json_file.flush()
    api.upload_aws(out_file, metadata,
                   oh_member.access_token,
                   project_member_id=oh_member.oh_id)
    logger.debug('uploaded new file for {}'.format(oh_member.oh_id))


def remove_partial_data(moves_data, start_date):
    remove_indexes = []
    for i, element in enumerate(moves_data):
        element_date = datetime.strptime(
                                element['date'], "%Y%m%d").isocalendar()[:2]
        if element_date == start_date:
            remove_indexes.append(i)
    for index in sorted(remove_indexes, reverse=True):
        del moves_data[index]
    return moves_data


def get_start_date(moves_data, moves_access_token):
    if moves_data == []:
        url = MOVES_API_BASE + "/user/profile?access_token={}".format(
                                        moves_access_token
        )
        response = rr.get(url, wait=True, realms=['moves'])
        return response.json()['profile']['firstDate']
    else:
        return moves_data[-1]['date']


def get_existing_moves(oh_access_token):
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'Moves' in dfile['metadata']['tags']:
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            moves_data = json.load(open(tf_in.name))
            return moves_data
    return []
