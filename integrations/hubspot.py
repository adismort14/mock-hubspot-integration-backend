# hubspot.py

from fastapi import Request, HTTPException
import os
import json
import secrets
import base64
import asyncio
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse
import httpx

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
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    return f'{AUTHORIZATION_URL}&state={encoded_state}'

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
            raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    
    original_state = state_data.get('state')
    # print('--------------------------------------')
    # print(original_state)
    # print('--------------------------------------')
    
    
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret':CLIENT_SECRET,
                    'redirect_uri': REDIRECT_URI,
                    'code': code
                }, 
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}'),
        )

    print(response.json())
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    # TODO
    pass

async def create_integration_item_metadata_object(response_json):
    # TODO
    pass

async def get_items_hubspot(credentials):
    # TODO
    pass