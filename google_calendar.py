import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

creds_json = os.getenv('GOOGLE_CREDENTIALS')
if not creds_json:
    raise Exception("GOOGLE_CREDENTIALS не задана")

creds_dict = json.loads(creds_json)
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

# Замените на ID вашего календаря
CALENDAR_ID = 'ваш_идентификатор_календаря'

def get_calendar_service():
    return build('calendar', 'v3', credentials=creds)

def create_event(service, summary, description, start_dt, end_dt):
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'Europe/Moscow',
        },
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created.get('id')