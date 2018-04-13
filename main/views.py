import logging
import requests
import os
import base64
import json
import arrow

from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.conf import settings
from datauploader.tasks import xfer_to_open_humans
from open_humans.models import OpenHumansMember
from .models import DataSourceMember
from demotemplate.settings import rr


# Set up logging.
logger = logging.getLogger(__name__)


def index(request):
    """
    Starting page for app.
    """

    context = {'client_id': settings.OPENHUMANS_CLIENT_ID,
               'oh_proj_page': settings.OH_ACTIVITY_PAGE}

    return render(request, 'main/index.html', context=context)


def complete(request):
    """
    Receive user from Open Humans. Store data, start upload.
    """
    print("Received user returning from Open Humans.")
    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    oh_member = oh_code_to_member(code=code)

    if oh_member:
        # Log in the user.
        user = oh_member.user
        login(request, user,
              backend='django.contrib.auth.backends.ModelBackend')

        # Initiate a data transfer task, then render `complete.html`.
        # xfer_to_open_humans.delay(oh_id=oh_member.oh_id)
        context = {'oh_id': oh_member.oh_id,
                   'oh_proj_page': settings.OH_ACTIVITY_PAGE}
        if not hasattr(oh_member, 'datasourcemember'):
            moves_url = ('https://api.moves-app.com/oauth/v1/authorize?'
                         'response_type=code&scope=activity location&'
                         'redirect_uri={}&client_id={}').format(
                            settings.MOVES_REDIRECT_URI,
                            settings.MOVES_CLIENT_ID)
            context['moves_url'] = moves_url
        return render(request, 'main/complete.html',
                      context=context)

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def moves_complete(request):
    """
    Receive user from Moves. Store data, start processing.
    """
    logger.debug("Received user returning from Moves.")
    # Exchange code for token.
    # This creates an OpenHumansMember and associated user account.
    code = request.GET.get('code', '')
    ohmember = request.user.oh_member
    moves_member = moves_code_to_member(code=code, ohmember=ohmember)

    if moves_member:
        return render(request, 'main/moves_complete.html')

    logger.debug('Invalid code exchange. User returned to starting page.')
    return redirect('/')


def moves_code_to_member(code, ohmember):
    """
    Exchange code for token, use this to create and return Moves members.
    If a matching moves exists, update and return it.
    """
    print("FOOBAR.")
    if settings.MOVES_CLIENT_SECRET and \
       settings.MOVES_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri': settings.MOVES_REDIRECT_URI,
            'code': code,
            'client_id': settings.MOVES_CLIENT_ID,
            'client_secret': settings.MOVES_CLIENT_SECRET
        }
        req = requests.post(
            'https://api.moves-app.com/oauth/v1/access_token'.format(
                settings.OPENHUMANS_OH_BASE_URL),
            data=data
        )
        data = req.json()
        print(data)
        if 'access_token' in data:
            try:
                moves_member = DataSourceMember.objects.get(
                    moves_id=data['user_id'])
                logger.debug('Member {} re-authorized.'.format(
                    moves_member.moves_id))
                moves_member.access_token = data['access_token']
                moves_member.refresh_token = data['refresh_token']
                moves_member.token_expires = DataSourceMember.get_expiration(
                    data['expires_in'])
                print('got old moves member')
            except DataSourceMember.DoesNotExist:
                moves_member = DataSourceMember(
                    moves_id=data['user_id'],
                    access_token=data['access_token'],
                    refresh_token=data['refresh_token'],
                    token_expires=DataSourceMember.get_expiration(
                        data['expires_in'])
                        )
                moves_member.user = ohmember
                logger.debug('Member {} created.'.format(data['user_id']))
                print('make new moves member')
            moves_member.save()

            return moves_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in Moves response!')
    else:
        logger.error('MOVES_CLIENT_SECRET or code are unavailable')
    return None


def oh_code_to_member(code):
    """
    Exchange code for token, use this to create and return OpenHumansMember.
    If a matching OpenHumansMember exists, update and return it.
    """
    if settings.OPENHUMANS_CLIENT_SECRET and \
       settings.OPENHUMANS_CLIENT_ID and code:
        data = {
            'grant_type': 'authorization_code',
            'redirect_uri':
            '{}/complete'.format(settings.OPENHUMANS_APP_BASE_URL),
            'code': code,
        }
        req = requests.post(
            '{}/oauth2/token/'.format(settings.OPENHUMANS_OH_BASE_URL),
            data=data,
            auth=requests.auth.HTTPBasicAuth(
                settings.OPENHUMANS_CLIENT_ID,
                settings.OPENHUMANS_CLIENT_SECRET
            )
        )
        data = req.json()

        if 'access_token' in data:
            oh_id = oh_get_member_data(
                data['access_token'])['project_member_id']
            try:
                oh_member = OpenHumansMember.objects.get(oh_id=oh_id)
                logger.debug('Member {} re-authorized.'.format(oh_id))
                oh_member.access_token = data['access_token']
                oh_member.refresh_token = data['refresh_token']
                oh_member.token_expires = OpenHumansMember.get_expiration(
                    data['expires_in'])
            except OpenHumansMember.DoesNotExist:
                oh_member = OpenHumansMember.create(
                    oh_id=oh_id,
                    access_token=data['access_token'],
                    refresh_token=data['refresh_token'],
                    expires_in=data['expires_in'])
                logger.debug('Member {} created.'.format(oh_id))
            oh_member.save()

            return oh_member

        elif 'error' in req.json():
            logger.debug('Error in token exchange: {}'.format(req.json()))
        else:
            logger.warning('Neither token nor error info in OH response!')
    else:
        logger.error('OH_CLIENT_SECRET or code are unavailable')
    return None


def oh_get_member_data(token):
    """
    Exchange OAuth2 token for member data.
    """
    req = requests.get(
        '{}/api/direct-sharing/project/exchange-member/'
        .format(settings.OPENHUMANS_OH_BASE_URL),
        params={'access_token': token}
        )
    if req.status_code == 200:
        return req.json()
    raise Exception('Status code {}'.format(req.status_code))
    return None
