
from datetime import datetime


def is_valid_sighting(sighting):
    if not isinstance(sighting, dict):
        return False

    for field in ["id", "date", "location"]:
        value = sighting.get(field)

        if not isinstance(value, str) or not value.strip():
            return False

    try:
        datetime.fromisoformat(sighting["date"])
    except ValueError:
        return False

    return True

def process_sightings(sightings):
    valid_sightings = []
    seen_ids = set()
    invalid_count = 0
    duplicate_count = 0

    for sighting in sightings:
        if not is_valid_sighting(sighting):
            invalid_count += 1
            continue

        sighting_id = sighting["id"]

        if sighting_id in seen_ids:
            duplicate_count += 1
            continue

        seen_ids.add(sighting_id)
        valid_sightings.append(sighting)

    return {
        "received": len(sightings),
        "count": len(valid_sightings),
        "invalid_removed": invalid_count,
        "duplicates_removed": duplicate_count,
        "sightings": valid_sightings,
    }
    
def filter_by_location(sightings, location):
    if location is None:
        return sightings

    location = location.strip().casefold()
    filtered_sightings = []

    for sighting in sightings:
        if sighting["location"].strip().casefold() == location:
            filtered_sightings.append(sighting)

    return filtered_sightings

def filter_by_date(sightings, start_date=None, end_date=None):
    if start_date is None and end_date is None:
        return sightings

    filtered_sightings = []

    for sighting in sightings:
        sighting_date = datetime.fromisoformat(sighting["date"]).date()

        if start_date is not None and sighting_date < start_date:
            continue

        if end_date is not None and sighting_date > end_date:
            continue

        filtered_sightings.append(sighting)

    return filtered_sightings