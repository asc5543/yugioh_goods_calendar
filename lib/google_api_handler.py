"""
Utility for handing Google Calendar.
Author: asc5543
"""

import datetime
import json
import os
import tempfile

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

def generate_account_json_file(project_id: str):
  # API credentials
  private_key_id = os.environ['PRIVATE_KEY_ID']
  private_key = os.environ['PRIVATE_KEY'].replace('\\n', '\n')
  client_email = os.environ['CLIENT_EMAIL']
  client_id = os.environ['CLIENT_ID']
  client_x509_cert_url = os.environ['CLIENT_URL']
  _config = {
      "type": "service_account",
      "project_id": project_id,
      "private_key_id": private_key_id,
      "private_key": private_key,
      "client_email": client_email,
      "client_id": client_id,
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": client_x509_cert_url,
      "universe_domain": "googleapis.com",
  }
  tmp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
  json.dump(_config, tmp_file)
  tmp_file.flush()
  return tmp_file.name

class GoogleCalendarHandler:
  def __init__(self, account_file: str, calendar_id: str):
    # Calendar API credentials
    self.scopes = ['https://www.googleapis.com/auth/calendar']
    self.service_account_file = account_file  # Path to your Google API credentials JSON file
    self.calendar_id = calendar_id
    # Create a service object for the Google Calendar API
    self.credentials = Credentials.from_service_account_file(self.service_account_file, scopes=self.scopes)
    self.calendar_service = build('calendar', 'v3', credentials=self.credentials)

  def get_all_calendar_event_summary(self) -> list[str]:
    """Get all events of the calendar."""
    calendar_events = []
    page_token = None
    while True:
      events_result = self.calendar_service.events().list(
        calendarId=self.calendar_id,
        pageToken=page_token,
      ).execute()

      for event in events_result['items']:
        if 'summary' in event:
          calendar_events.append(event['summary'])

      page_token = events_result.get('nextPageToken')
      if not page_token:
        break

    return calendar_events

  def get_calendar_event_by_summary(self, summary: str) -> dict:
    """Get event by summary."""
    page_token = None
    while True:
      events_result = self.calendar_service.events().list(
        calendarId=self.calendar_id,
        q=summary,
        pageToken=page_token,
      ).execute()

      for event in events_result['items']:
        if event['summary'] == summary:
          return event

      page_token = events_result.get('nextPageToken')
      if not page_token:
        break

    return {}

  # Function to create a calendar event with a Yugioh good
  def create_calendar_event(self,
                            summary: str,
                            description: str,
                            good_release_date: datetime.date) -> str:
    """Create a calendar event."""
    event = {
      'summary': summary,
      'description': description,
      'start': {'date': good_release_date.isoformat(),},
      'end': {'date': good_release_date.isoformat(),},
    }

    try:
      # Create the event
      created_event = self.calendar_service.events().insert(
        calendarId=self.calendar_id,
        body=event
      ).execute()

      event_id = created_event.get('id')
      print(f"Successfully created event: '{summary}' on {good_release_date} (ID: {event_id})")
      return event_id

    except Exception as e:
      print(f"Failed to create event '{summary}': {e}")
      return ""

  def update_calendar_event(self, summary: str, description: str) -> bool:
    """Update a calendar event."""

    event = self.get_calendar_event_by_summary(summary)
    if not event:
      print(f"Cannot find the event: {summary}, cannot be updated")
      return False

    if event['description'] == description:
      print('The description is the same, no need to be updated')
      return True
    event['description'] = description

    # Update the event
    try:
      self.calendar_service.events().patch(
        calendarId=self.calendar_id,
        eventId=event['id'],
        body=event,
      ).execute()
      print(f"Update the event succeed: {summary}")
      return True
    except Exception as e:
      print(f"Update the event fail with: {e}")
      return False

  def delete_calendar_event(self, summary: str) -> bool:
    """Delete a calendar event by summary."""
    event = self.get_calendar_event_by_summary(summary)

    if not event or 'id' not in event:
      print(f"Cannot find: {summary}, delete fail.")
      return False

    try:
      self.calendar_service.events().delete(
        calendarId=self.calendar_id,
        eventId=event['id']
      ).execute()
      print(f"Delete the event succeed: {summary}")
      return True
    except Exception as e:
      print(f"Delete the event fail with: {e}")
      return False

if __name__ == '__main__':
  service_account_file = generate_account_json_file("yugioh-goods-calendar")
  cal_id = os.environ['CALENDAR_ID']
  calendar_handler = GoogleCalendarHandler(
    service_account_file,
    cal_id,
  )
  date = datetime.date.today()
  calendar_handler.create_calendar_event("test", "test", date)
  calendar_handler.create_calendar_event("test2", "test2", date)
  calendar_handler.update_calendar_event("test", "test123")
  calendar_handler.delete_calendar_event("test2")