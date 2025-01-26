### What is this?

Neat little project to implement OAuth 2.0 and brush up my Python skills.

### How to run:

Add the Hubspot app (from dev account) CLIENT_SECRET and CLIENT_ID in a new .env file in the backend/integrations directory.

Backend :
- `pip install -r requirements.txt`
- `uvicorn main:app --reload`

Frontend :
- `npm i`
- `npm run start`

### Future Improvements:

- use Hubspot Python SDK
- create an internal package instead exposing custom APIs (which internally use hubspot sdk)
- store the Access Token in DB (if any) in encrypted form
- Add support for more entities like tickets

- refactor frontend into smaller components
- refactor backend -> utils package

