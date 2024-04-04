import json
import os
import time

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from dotenv import load_dotenv


## you can run this with python manage.py fetch_teamup
## output gets saved to teamup_event_data_by_boopkinggroup.json in root
## you ned TEAMUP_API_KEY in .env or add --key TEAMUP_API_KEY argument
class Command(BaseCommand):
    help = "fetch booking data of teamup of 2024 and sort it by bookinggroup"
    load_dotenv()
    teamup_api_key = os.getenv("TEAMUP_API_KEY", None)

    def add_arguments(self, parser):
        # Positional arguments
        # parser.add_argument("poll_ids", nargs="+", type=int)

        # Named (optional) arguments
        parser.add_argument(
            "--key",
            action="store",
            help="Teamup API KEY",
        )

        parser.add_argument(
            "--calendar",
            action="store",
            help="Teamup calendar Key orId",
        )

    def handle(self, *args, **options):
        # ...
        if options.get("key"):
            self.teamup_api_key = options["key"]

        if not options.get("calendar"):
            raise ValueError("The --calendar tag is required.")

        if self.teamup_api_key:
            events2024 = self.get_teamup_events()
            if type(events2024) == list:
                self.stdout.write(f"fetched {len(events2024)} events")

                ## sort events by series_id which is the same as bookinggroup
                sorted_events = {}
                new_series_id_counter = 1
                for event in events2024:
                    if event["series_id"] is None:
                        event["series_id"] = new_series_id_counter
                        new_series_id_counter += 1

                    series_id = event["series_id"]
                    sorted_events.setdefault(series_id, []).append(event)

                file_name = time.strftime("%Y%m%d-%H%M%S") + ".json"

                try:
                    sorted_events_json = json.dumps(
                        sorted_events,
                        ensure_ascii=False,
                        indent=4,
                    )

                    # Speichere den JSON-String in einer Datei.
                    # Da default_storage.save einen Namen und ein ContentFile (oder ähnliches) erwartet,
                    # verwenden wir ContentFile, um den JSON-String zu speichern.
                    cachfile = default_storage.save(
                        f"teamup/{file_name}",
                        ContentFile(sorted_events_json.encode("utf-8")),
                    )

                    self.stdout.write(
                        self.style.SUCCESS(f"Successfully wrote to {file_name}"),
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error writing to {file_name}: {e}"),
                    )
        else:
            self.stdout.write("no Teamup Api Key")

    def get_teamup_events(self):
        import http.client
        import json
        import re

        # Definiere die Verbindung und Header
        conn = http.client.HTTPSConnection("api.teamup.com")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Teamup-Token": self.teamup_api_key,
        }

        # Sende die Anfrage
        conn.request(
            "GET",
            "/ksn1y3bu4h7uckv547/events?startDate=1.1.2024&endDate=31.12.2024",
            headers=headers,
        )

        # Lese die Antwort
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        data = json.loads(data)
        self.stdout.write(str(res.status))
        # Überprüfe, ob ein Fehler aufgetreten ist
        if res.status != 200 and res.status != 201:
            # Parsen der Fehlermeldung
            error_id = data["error"]["id"]
            error_title = data["error"]["title"]
            error_message = data["error"]["message"]
            # Entferne HTML-Tags aus der Fehlermeldung
            error_message_clean = re.sub(r"<.*?>", "", error_message)

            # Ausgabe der Fehlerdetails
            self.stdout.write("Error ID:", error_id)
            self.stdout.write("Error Title:", error_title)
            self.stdout.write("Error Message:", error_message_clean)
            conn.close()
            return False

        else:
            # Wenn keine Fehler auftreten, gib die Antwort in der Konsole aus
            # print(data)
            conn.close()
            if "events" in data:
                return data["events"]
            else:
                return False
