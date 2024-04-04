import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from roomsharing.bookings.models import Booking
from roomsharing.bookings.models import BookingGroup
from roomsharing.rooms.models import Room


## you can run this with ython manage.py experiment_teamup_import
## it reads: teamup_event_data_by_boopkinggroup.json in root
class Command(BaseCommand):
    help = "read media/temup-"

    # def add_arguments(self, parser):
    #     # Positional arguments
    #     # parser.add_argument("poll_ids", nargs="+", type=int)

    #     # Named (optional) arguments
    #     parser.add_argument(
    #         "--key",
    #         action="store",
    #         help="Teamup API KEY",
    #     )

    def handle(self, *args, **options):
        sorted_events = read_latest_teamup_json()
        if sorted_events:
            # notice some events have multiple subcalenders/rooms
            for group_index, group in enumerate(sorted_events):
                if group_index >= 10:  # Limit to the first group only
                    break

                g = BookingGroup(title=sorted_events[group][0]["title"])
                try:
                    g.full_clean()
                except ValidationError as e:
                    print(f"Validation error for Group {g.title}: {e.message_dict}")

                print(
                    f"{sorted_events[group][0]['title']} ({len(sorted_events[group])} Bookings)",
                )

                for booking_index, booking in enumerate(sorted_events[group]):
                    b = Booking(
                        booking_group=g,
                        timespan=(
                            datetime.strptime(
                                booking["start_dt"],
                                "%Y-%m-%dT%H:%M:%S%z",
                            ),
                            datetime.strptime(
                                booking["end_dt"],
                                "%Y-%m-%dT%H:%M:%S%z",
                            ),
                        ),
                        room=Room.objects.get(name="Co-Working-Space"),
                    )
                    try:
                        b.full_clean()
                    except ValidationError as e:
                        print(f"Validation error for Booking: {e.message_dict}")

                    start_dt = datetime.strptime(
                        booking["start_dt"],
                        "%Y-%m-%dT%H:%M:%S%z",
                    ).strftime("%Y-%m-%d %H:%M")
                    end_dt = datetime.strptime(
                        booking["end_dt"],
                        "%Y-%m-%dT%H:%M:%S%z",
                    ).strftime("%Y-%m-%d %H:%M")
                    booking_details = f"    {booking['id']}, {booking['title']}, {start_dt}, {end_dt}, {booking['subcalendar_id']}"
                    print(booking_details)
                    if booking_index >= 4:  # Limit to the first booking only
                        break


def read_latest_teamup_json():
    # Liste alle 'teamup-' Dateien auf
    all_files = default_storage.listdir("teamup")[
        1
    ]  # Das listdir Argument hängt von deiner Speicherstruktur ab
    teamup_files = [f for f in all_files if f.endswith(".json")]

    if not teamup_files:
        print("Keine Teamup-Dateien gefunden.")
        return None

    # Sortiere die Dateien basierend auf dem Zeitstempel im Namen
    latest_file = sorted(
        teamup_files,
        key=lambda x: x.split("-")[1].split(".")[0],
        reverse=True,
    )[0]

    # Versuche, den Inhalt der neuesten Datei zu lesen
    try:
        with default_storage.open("teamup/" + latest_file, "r") as file:
            content = file.read()
            # Konvertiere den JSON-String zurück in ein Python-Objekt
            return json.loads(content)
    except Exception as e:
        print(f"Fehler beim Lesen der Datei {latest_file}: {e}")
        return None
