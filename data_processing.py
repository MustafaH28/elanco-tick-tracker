"""Clean and filter the sighting records used by the Elanco Tick Tracker.

Elanco supplies raw records, which may contain missing values, invalid dates or
repeated IDs. This module handles those data-quality issues before sightings
are returned to a caller or included in regional and time-based reports.

The processing order is important:
validate each record -> keep the first valid record for each ID ->
filter the cleaned records by location and calendar date.
"""

# Read ISO-formatted dates so we can check that source dates are usable and
# compare their calendar-date portion with the user's chosen date range.
from datetime import datetime


def is_valid_sighting(sighting):
    """Check whether one record contains the minimum information we need.

    An ID identifies the sighting report and allows duplicate detection.
    A usable date supports date filtering and weekly/monthly reporting.
    A location supports location filtering and regional reporting.

    species and latinName are optional for these features, so their absence
    does not cause an otherwise usable sighting to be discarded.
    """
    # A JSON record should become a Python dictionary. Reject other values,
    # such as None, a string or a list, before attempting to read named fields.
    if not isinstance(sighting, dict):
        return False

    # Check every required field. get() returns None if the field is missing.
    # Each value must be text and must contain something besides whitespace.
    # Checking the type first also makes it safe to call strip() afterwards.
    for field in ["id", "date", "location"]:
        value = sighting.get(field)

        if not isinstance(value, str) or not value.strip():
            return False

    # A non-empty date string can still be unusable, such as "not-a-date" or
    # an impossible calendar date. Try parsing it; reject it if parsing fails.
    # We only check the date here, leaving the original record unchanged.
    try:
        datetime.fromisoformat(sighting["date"])
    except ValueError:
        return False

    # Reaching this point means the record passed all of our minimum checks.
    # These checks establish usability, not whether a sighting is factually
    # correct or whether its location exists in the region mapping.
    return True


def process_sightings(sightings):
    """Remove unusable records and repeated valid IDs from a batch.

    main.py checks that the upstream response is a list before calling this
    function. Here we check the individual records inside that list.

    Keep the first valid occurrence of each exact ID. If an invalid record
    appears before a valid one with that ID, the valid one can still be kept.
    Return the cleaned list with counters explaining what happened to the batch.
    """
    # Keep accepted records in their original order. A set tracks accepted IDs
    # so duplicate detection does not require searching the kept list each time.
    # The list and set grow as unique valid sightings are accepted into memory.
    valid_sightings = []
    seen_ids = set()

    # Separate counters make data-quality problems visible in API responses.
    # A record is classified as invalid, duplicate or accepted, in that order.
    invalid_count = 0
    duplicate_count = 0

    for sighting in sightings:
        # Validate before checking duplicates. An unusable record is counted
        # as invalid and cannot reserve its ID or enter any subsequent report.
        # continue skips the rest of this iteration and checks the next record.
        if not is_valid_sighting(sighting):
            invalid_count += 1
            continue

        sighting_id = sighting["id"]

        # IDs are compared exactly as supplied. An ID already in seen_ids
        # belongs to an accepted record, so keep that first valid record and
        # count this later occurrence as a duplicate rather than counting twice.
        if sighting_id in seen_ids:
            duplicate_count += 1
            continue

        # Record this newly accepted ID, then keep the original dictionary.
        # Keeping the dictionary also preserves any optional fields, such as
        # species or latinName, that Elanco included in the source record.
        seen_ids.add(sighting_id)
        valid_sightings.append(sighting)

    # received is the original batch size; count is the cleaned size at this
    # stage, before location/date filtering. The two removal counters describe
    # the whole batch. main.py later updates count to the filtered size while
    # retaining these source-data counters.
    return {
        "received": len(sightings),
        "count": len(valid_sightings),
        "invalid_removed": invalid_count,
        "duplicates_removed": duplicate_count,
        "sightings": valid_sightings,
    }


def filter_by_location(sightings, location):
    """Keep cleaned sightings whose location matches the requested location.

    Compare the complete location names, ignoring surrounding whitespace and
    differences in capitalisation. This is an exact-name match, not a partial
    search: "London" matches "lOnDoN" but a query of "Lon" does not match London.
    """
    # No supplied location means no location restriction. Return all records
    # passed to this function rather than making the caller choose a city.
    if location is None:
        return sightings

    # Apply the same normalisation to the query and each stored location.
    # strip() removes surrounding whitespace; casefold() supports comparison
    # without capitalisation differences. Original record values are preserved.
    location = location.strip().casefold()
    filtered_sightings = []

    for sighting in sightings:
        # These records have already passed validation, so location is a
        # non-empty string. Add only records whose normalised names match.
        if sighting["location"].strip().casefold() == location:
            filtered_sightings.append(sighting)

    # A location with no matches produces an empty list. A blank query also
    # matches none of the validated locations; only None disables the filter.
    return filtered_sightings


def filter_by_date(sightings, start_date=None, end_date=None):
    """Keep cleaned sightings inside an optional, inclusive calendar-date range.

    start_date and end_date are Python date objects, or None for an open limit.
    main.py's endpoints parse these inputs and reject a reversed range before
    calling this helper. Either limit can also be used on its own.

    Compare the calendar date written in each record, without converting time
    zones. Both boundary days are included, regardless of their time of day.
    """
    # Without either limit, there is no date restriction to apply.
    if start_date is None and end_date is None:
        return sightings

    filtered_sightings = []

    for sighting in sightings:
        # Source dates may include a clock time. Extract just the calendar
        # date so a sighting at 23:59 on the end date is still included.
        # Earlier validation ensures the source value can be parsed here.
        sighting_date = datetime.fromisoformat(sighting["date"]).date()

        # Exclude records strictly before the start date when one is supplied.
        # Using < rather than <= keeps records on the start date itself.
        if start_date is not None and sighting_date < start_date:
            continue

        # Exclude records strictly after the end date when one is supplied.
        # Using > rather than >= keeps records on the end date itself.
        if end_date is not None and sighting_date > end_date:
            continue

        # Records reach this line only if they pass every supplied date limit.
        # Preserve their original order and leave their field values unchanged.
        filtered_sightings.append(sighting)

    return filtered_sightings
