# hubspot.py

from fastapi import Request
import os
import json
import secrets
import base64
from dotenv import load_dotenv

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
BASE_AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
SCOPE = '%20'.join(['oauth','crm.objects.contacts.read'])
AUTHORIZATION_URL=f'{BASE_AUTHORIZATION_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPE}'

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)
    # print(f'{AUTHORIZATION_URL}&state={encoded_state}')
    return f'{AUTHORIZATION_URL}&state={encoded_state}'

async def oauth2callback_hubspot(request: Request):
    # TODO
    pass

async def get_hubspot_credentials(user_id, org_id):
    # TODO
    pass

async def create_integration_item_metadata_object(response_json):
    # TODO
    pass

async def get_items_hubspot(credentials):
    # TODO
    pass