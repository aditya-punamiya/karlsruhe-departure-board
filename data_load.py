"""Loads GTFS timetable data once and answers departure queries from memory."""
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"]

# These dictionaries are filled ONCE by load_data(). After that they are only read.
stops = {}                                 # stop_id    -> stop_name
routes = {}                                # route_id   -> {"name": ..., "type": ...}
trips = {}                                 # trip_id    -> {"route_id", "headsign", "service_id"}
calendar = {}                              # service_id -> start, end and a flag per weekday
calendar_dates = defaultdict(list)         # "YYYYMMDD" -> [(service_id, exception_type), ...]
departures_by_stop = defaultdict(list)     # stop_id    -> [(seconds_after_midnight, trip_id), ...]


def read_csv(filename, required=True):
    """Yield every row of a GTFS file as a dictionary (column name -> value)."""
    path = DATA_DIR / filename
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing GTFS file: {path}")
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def time_to_seconds(time_str):
    """'08:15:30' -> seconds since midnight. GTFS allows hours >= 24 for after-midnight trips."""
    hours, minutes, seconds = time_str.strip().split(":")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def load_data():
    """Read all needed GTFS files once. This is the slow part (seconds), so call it only at startup."""
    for store in (stops, routes, trips, calendar, calendar_dates, departures_by_stop):
        store.clear()

    for row in read_csv("stops.txt"):
        stops[row["stop_id"]] = row["stop_name"]

    for row in read_csv("routes.txt"):
        routes[row["route_id"]] = {
            "name": row.get("route_short_name", ""),
            "type": row.get("route_type", ""),
        }

    for row in read_csv("trips.txt"):
        trips[row["trip_id"]] = {
            "route_id": row["route_id"],
            "headsign": row.get("trip_headsign", ""),
            "service_id": row["service_id"],
        }

    # calendar.txt and calendar_dates.txt: on which days does each service_id run?
    for row in read_csv("calendar.txt", required=False):
        calendar[row["service_id"]] = {
            "start": row["start_date"],
            "end": row["end_date"],
            **{day: row[day] for day in WEEKDAYS},
        }
    for row in read_csv("calendar_dates.txt", required=False):
        calendar_dates[row["date"]].append((row["service_id"], row["exception_type"]))

    # The big file: sort every departure into a list per stop_id.
    for row in read_csv("stop_times.txt"):
        try:
            seconds = time_to_seconds(row["departure_time"])
        except ValueError:
            continue  # empty or malformed time
        departures_by_stop[row["stop_id"]].append((seconds, row["trip_id"]))


def active_services(day):
    """Set of service_ids that run on the given date."""
    date_str = day.strftime("%Y%m%d")
    weekday = WEEKDAYS[day.weekday()]

    active = {
        service_id
        for service_id, c in calendar.items()
        if c["start"] <= date_str <= c["end"] and c[weekday] == "1"
    }
    # Exceptions: 1 = service added on this date, 2 = service removed
    for service_id, exception_type in calendar_dates.get(date_str, []):
        if exception_type == "1":
            active.add(service_id)
        elif exception_type == "2":
            active.discard(service_id)
    return active


def get_departures(search_term, now=None):
    """Return {station_name: [up to 4 next departures]}. Only dictionary lookups, no file access."""
    now = now or datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    active = active_services(now.date())
    term = search_term.lower()

    found = defaultdict(list)
    for stop_id, stop_name in stops.items():
        if term not in stop_name.lower():
            continue

        for seconds, trip_id in departures_by_stop.get(stop_id, []):
            trip = trips.get(trip_id)
            if trip is None or trip["service_id"] not in active:
                continue

            departure = midnight + timedelta(seconds=seconds)
            minutes_left = int((departure - now).total_seconds() // 60)
            if minutes_left < 0:
                continue

            route = routes.get(trip["route_id"], {})
            line = route.get("name") or "?"
            destination = trip["headsign"].strip()
            if destination.startswith(line + " "):
                destination = destination[len(line) + 1:].strip()
            if not destination:
                destination = "–"

            found[stop_name].append({
                "line": line,
                "destination": destination,
                "time": departure.strftime("%H:%M"),
                "minutes": minutes_left,
                "route_type": route.get("type", ""),
                "sort_dt": departure,
            })

    results = {}
    for station, deps in found.items():
        deps.sort(key=lambda d: d["sort_dt"])
        seen = set()
        unique = []
        for d in deps:
            key = (d["line"], d["destination"], d["time"])
            if key not in seen:
                seen.add(key)
                unique.append(d)
        results[station] = unique[:4]
    return results