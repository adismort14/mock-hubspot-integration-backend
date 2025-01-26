# hubspot.py

import os
import json
import secrets
import base64
import asyncio
import httpx
from enum import Enum
from typing import List, Optional
from fastapi import Request, HTTPException
from datetime import datetime
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
BASE_AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'

# Assign appropriate scopes according to the searchable entities
# @see HubSpotObjectType
SCOPE = '%20'.join(['oauth','crm.objects.contacts.read','crm.objects.companies.read','crm.objects.deals.read'])

async def authorize_hubspot(user_id: str, org_id: str) -> str:
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    return f'{BASE_AUTHORIZATION_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPE}&state={encoded_state}'

async def oauth2callback_hubspot(request: Request) -> HTMLResponse:
    if request.query_params.get('error'):
            raise HTTPException(status_code=400, detail=request.query_params.get('error'))
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))
    
    original_state = state_data.get('state')
    
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

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)
    
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id: str, org_id: str) -> dict:
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='Invalid credentials.')
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

class HubSpotObjectType(Enum):
    CONTACTS = 'contacts'
    COMPANIES = 'companies'
    DEALS = 'deals'

def create_integration_item_metadata_object(object: dict, objectType: str) -> IntegrationItem:
    properties = object.get('properties', {})
    
    return IntegrationItem(
        id=object.get('id'),
        type=objectType, 
        name=get_hubspot_object_name(properties, objectType),
        creation_time=parse_hubspot_timestamp(properties.get('createdate')),
        last_modified_time=parse_hubspot_timestamp(properties.get('lastmodifieddate')),
    )

def parse_hubspot_timestamp(timestamp: Optional[str]) -> Optional[str]:
    if not timestamp:
        return None
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y at %I:%M %p")
    
    except (ValueError, TypeError):
        return None
    
def get_hubspot_object_name(properties: dict, objectType: str) -> str:
    try:
        object_type_enum = HubSpotObjectType(objectType)
    except ValueError:
        return properties.get('name', 'Unnamed')

    if object_type_enum == HubSpotObjectType.CONTACTS:
        first_name = properties.get('firstname', '').strip()
        last_name = properties.get('lastname', '').strip()
        
        if not first_name and not last_name:
            return 'Unnamed Contact' 
        else:
            return f"{first_name} {last_name}"
    elif object_type_enum == HubSpotObjectType.DEALS:
        return properties.get('dealname','Unnamed Deal')
    else:
        return properties.get('name', 'Unnamed')

async def fetch_all_objects(credentials: dict, object_type: str) -> List[IntegrationItem]:
    async with httpx.AsyncClient() as client:
        integration_items = []
        offset = 0
        limit = 100
        
        while True:
            params = {
                "limit": limit,
                "archived": False,
                "offset": offset
            }
            
            headers = {
                'Authorization': f'Bearer {credentials.get("access_token")}',
                'Content-Type': 'application/json'
            }
            
            response = await client.get(
                f'https://api.hubapi.com/crm/v3/objects/{object_type}', 
                params=params, 
                headers=headers
            )
            
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            items = [
                create_integration_item_metadata_object(item, object_type) 
                for item in results
            ]
            
            integration_items.extend(items)
            
            if len(results) < limit:
                break
            
            offset += limit
        
        return integration_items
    
async def get_items_hubspot(credentials: str) -> list:
    credentials = json.loads(credentials)
    
    standard_objects = [
        'contacts', 
        'companies', 
        'deals',
    ]
    
    tasks = [fetch_all_objects(credentials, object_type) for object_type in standard_objects]
    
    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]