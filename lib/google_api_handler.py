"""
Utility for handing Google Calendar API interactions.
Author: asc5543
"""

import datetime
import json
import os
import tempfile
from typing import Dict, List

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def generate_account_json_file(project_id: str) -> str:
    """Generates a temporary Service Account JSON file from env vars."""
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
        "auth_provider_x509_cert_url":
            "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": client_x509_cert_url,
        "universe_domain": "googleapis.com",
    }

    tmp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
    json.dump(_config, tmp_file)
    tmp_file.flush()
    return tmp_file.name


class GoogleCalendarHandler:
    """Handler for Google Calendar API operations."""

    def __init__(self, account_file: str, calendar_id: str):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.service_account_file = account_file
        self.calendar_id = calendar_id

        # Initialize Google Calendar API service
        self.credentials = Credentials.from_service_account_file(
            self.service_account_file,
            scopes=self.scopes
        )
        self.calendar_service = build(
            'calendar', 'v3', credentials=self.credentials
        )

    def get_all_calendar_event_summary(self) -> List[str]:
        """Retrieves a list of all event summaries in the calendar."""
        calendar_events = []
        page_token = None
        while True:
            events_result = self.calendar_service.events().list(
                calendarId=self.calendar_id,
                pageToken=page_token,
            ).execute()

            for event in events_result.get('items', []):
                if 'summary' in event:
                    calendar_events.append(event['summary'])

            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        return calendar_events

    def get_calendar_event_by_summary(self, summary: str) -> Dict:
        """Finds a specific event object by exact summary match."""
        page_token = None
        while True:
            events_result = self.calendar_service.events().list(
                calendarId=self.calendar_id,
                q=summary,  # Use query parameter for efficiency
                pageToken=page_token,
            ).execute()

            for event in events_result.get('items', []):
                if event.get('summary') == summary:
                    return event

            page_token = events_result.get('nextPageToken')
            if not page_token:
                break

        return {}

    def create_calendar_event(
        self,
        summary: str,
        description: str,
        good_release_date: datetime.date
    ) -> str:
        """Creates an all-day calendar event."""
        event = {
            'summary': summary,
            'description': description,
            'start': {'date': good_release_date.isoformat()},
            'end': {'date': good_release_date.isoformat()},
        }

        try:
            created_event = self.calendar_service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()

            event_id = created_event.get('id')
            print(f"Event created: '{summary}' (ID: {event_id})")
            return event_id

        except Exception as e:
            print(f"Failed to create event '{summary}': {e}")
            return ""

    def update_calendar_event(self, summary: str, description: str) -> bool:
        """Updates the description of an existing event."""
        event = self.get_calendar_event_by_summary(summary)
        if not event:
            print(f"Event not found: {summary}, update aborted.")
            return False

        if event.get('description') == description:
            print(f'Description unchanged, skipping update: {summary}')
            return True

        event['description'] = description

        try:
            self.calendar_service.events().patch(
                calendarId=self.calendar_id,
                eventId=event['id'],
                body=event,
            ).execute()
            print(f"Update successful: {summary}")
            return True
        except Exception as e:
            print(f"Update failed: {summary}, Error: {e}")
            return False

    def delete_calendar_event(self, summary: str) -> bool:
        """Deletes an event by its summary."""
        event = self.get_calendar_event_by_summary(summary)

        if not event or 'id' not in event:
            print(f"Event not found: {summary}, deletion failed.")
            return False

        try:
            self.calendar_service.events().delete(
                calendarId=self.calendar_id,
                eventId=event['id']
            ).execute()
            print(f"Deletion successful: {summary}")
            return True
        except Exception as e:
            print(f"Deletion failed: {summary}, Error: {e}")
            return False


if __name__ == '__main__':
    # Smoke test
    tmp_json = generate_account_json_file("yugioh-goods-calendar")
    cal_id = os.environ.get('CALENDAR_ID')

    if cal_id:
        handler = GoogleCalendarHandler(tmp_json, cal_id)
        current_date = datetime.date.today()

        handler.create_calendar_event("Test Item", "Test Desc", current_date)
        handler.update_calendar_event("Test Item", "Updated Desc")
        handler.delete_calendar_event("Test Item")

    if os.path.exists(tmp_json):
        os.unlink(tmp_json)
