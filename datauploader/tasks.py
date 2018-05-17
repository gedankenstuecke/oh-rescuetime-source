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
import arrow

# Set up logging.
logger = logging.getLogger(__name__)

RESCUETIME_API = ('https://www.rescuetime.com/api/oauth/data'
                  '?perspective=interval&interval=minute&format=json&')


@shared_task
def process_rescuetime(oh_id):
    """
    Update the rescuetime file for a given OH user
    """
    logger.debug('Starting rescuetime processing for {}'.format(oh_id))
    oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
    oh_access_token = oh_member.get_access_token(
                            client_id=settings.OPENHUMANS_CLIENT_ID,
                            client_secret=settings.OPENHUMANS_CLIENT_SECRET)
    rescuetime_data = get_existing_rescuetime(oh_access_token)
    rescuetime_member = oh_member.datasourcemember
    rescuetime_access_token = rescuetime_member.access_token
    print('start update_rescuetime')
    update_rescuetime(oh_member, rescuetime_access_token, rescuetime_data)


def update_rescuetime(oh_member, rescuetime_access_token, rescuetime_data):
    #try:
    start_date = get_start_date(rescuetime_data, rescuetime_access_token)
    rescuetime_data = remove_partial_data(rescuetime_data, start_date)
    stop_date = datetime.utcnow()
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    counter = 0
    while start_date < stop_date:
        print('processing {} for member {}'.format(start_date,
                                                   oh_member.oh_id))
        query = RESCUETIME_API + \
            'access_token={}&restrict_begin={}&restrict_end={}'.format(
              rescuetime_access_token,
              datetime.strftime(start_date, "%Y-%m-%d"),
              datetime.strftime(start_date + timedelta(days=14),
                                "%Y-%m-%d"),
            )
        response = requests.get(query)
        response_json = response.json()
        print(rescuetime_data)
        print(response_json)
        if rescuetime_data == {}:
            rescuetime_data = response_json
        else:
            rescuetime_data['rows'] += response_json['rows ']
        start_date = start_date + timedelta(days=15)
        counter += 1
        if counter > 5:
            break
    print('successfully finished update for {}'.format(oh_member.oh_id))
    rescuetime_member = oh_member.datasourcemember
    rescuetime_member.last_updated = arrow.now().format()
    rescuetime_member.save()
#    except:
#        process_rescuetime.apply_async(args=[oh_member.oh_id], countdown=61)
#    finally:
    replace_rescuetime(oh_member, rescuetime_data)


def replace_rescuetime(oh_member, rescuetime_data):
    # delete old file and upload new to open humans
    tmp_directory = tempfile.mkdtemp()
    metadata = {
        'description':
        'RescueTime productivity data.',
        'tags': ['Rescuetime', 'productivity'],
        'updated_at': str(datetime.utcnow()),
        }
    out_file = os.path.join(tmp_directory, 'rescuetime.json')
    logger.debug('deleted old file for {}'.format(oh_member.oh_id))
    api.delete_file(oh_member.access_token,
                    oh_member.oh_id,
                    file_basename="rescuetime.json")
    with open(out_file, 'w') as json_file:
        json.dump(rescuetime_data, json_file)
        json_file.flush()
    api.upload_aws(out_file, metadata,
                   oh_member.access_token,
                   project_member_id=oh_member.oh_id)
    logger.debug('uploaded new file for {}'.format(oh_member.oh_id))


def remove_partial_data(rescuetime_data, start_date):
    if rescuetime_data != {}:
        for i, element in enumerate(rescuetime_data['rows']):
            if element[0][:10] == start_date:
                final_element = i
        rescuetime_data['rows'] = rescuetime_data['rows'][:final_element]
        return rescuetime_data
    return {}


def get_start_date(rescuetime_data, rescuetime_access_token):
    if rescuetime_data == {}:
        return "2016-07-01"
        # url = MOVES_API_BASE + "/user/profile?access_token={}".format(
        #                                 rescuetime_access_token
        # )
        # response = rr.get(url, wait=True, realms=['moves'])
        # return response.json()['profile']['firstDate']
    else:
        return rescuetime_data['rows'][-1][0][:10]


def get_existing_rescuetime(oh_access_token):
    member = api.exchange_oauth2_member(oh_access_token)
    for dfile in member['data']:
        if 'Rescuetime' in dfile['metadata']['tags']:
            # get file here and read the json into memory
            tf_in = tempfile.NamedTemporaryFile(suffix='.json')
            tf_in.write(requests.get(dfile['download_url']).content)
            tf_in.flush()
            rescuetime_data = json.load(open(tf_in.name))
            return rescuetime_data
    return {}
