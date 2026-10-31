"""Calculate the regional and time-based summaries required by the task.

main.py calls these functions after the data-processing step has validated
records, removed duplicate IDs and applied any location or date filters.
The functions then group those matching sightings and return lists of totals.

Keeping these calculations here gives every report a clear purpose and makes
the grouping rules easy to test separately from downloading the source data.
"""

# datetime reads each source timestamp; timedelta represents a number of days.
# Together they let us find the Monday that starts a sighting's calendar week.
from datetime import datetime, timedelta


# The source dataset provides city names rather than a separate region field.
# This explicit lookup gives the known cities a regional reporting group.
# English cities use English regions; Scottish and Welsh cities are grouped
# under Scotland and Wales. Keys are lowercase to match casefold() below.
# This is a fixed mapping for the dataset: new cities need an added entry to
# receive a named region; otherwise they are counted under "Unknown".
CITY_TO_REGION = {
    "birmingham": "West Midlands",
    "bristol": "South West",
    "cardiff": "Wales",
    "edinburgh": "Scotland",
    "glasgow": "Scotland",
    "leeds": "Yorkshire and the Humber",
    "leicester": "East Midlands",
    "liverpool": "North West",
    "london": "London",
    "manchester": "North West",
    "newcastle": "North East",  # Assumes Newcastle upon Tyne.
    "nottingham": "East Midlands",
    "sheffield": "Yorkshire and the Humber",
    "southampton": "South East",
}


def count_by_region(sightings):
    """Count matching sightings in each mapped region.

    This supplies the task's number-of-sightings-per-region report.
    The input should already be cleaned, deduplicated and filtered.
    Each input record contributes one count, including unmapped locations.
    An empty input produces an empty report rather than zero-count regions.
    """
    # Store a running total for each region encountered in the input records.
    # For example, Manchester and Liverpool both increase the North West total.
    region_counts = {}

    for sighting in sightings:
        # Normalise the city name for lookup so surrounding spaces and
        # capitalisation do not prevent a known city from finding its region.
        # This comparison does not alter the location in the original record.
        city = sighting["location"].strip().casefold()

        # An unmapped city is still a usable sighting. Keep it in an explicit
        # "Unknown" group so its count is not silently lost from the report.
        region = CITY_TO_REGION.get(city, "Unknown")

        # get(region, 0) starts a new region at zero; adding one counts this
        # sighting. Existing regions receive another one on their running total.
        region_counts[region] = region_counts.get(region, 0) + 1

    # Convert the running totals into a list of small dictionaries that
    # main.py can include in its JSON response. Alphabetical sorting gives
    # callers a consistent order, regardless of the order of source records.
    report = []

    for region in sorted(region_counts):
        report.append({
            "region": region,
            "count": region_counts[region],
        })

    return report


def count_by_period(sightings, period):
    """Count matching sightings by calendar week or calendar month.

    This supplies the task's trends-over-time report. Weekly groups run from
    Monday to Sunday; monthly groups cover their respective calendar month.
    period_start labels each group using its first date.

    Input records should already be cleaned and filtered. Only groups with
    matching sightings appear; empty input produces an empty report.
    """
    # main.py's Literal query parameter rejects unsupported API inputs.
    # This guard also protects direct calls to this helper, so a misspelt
    # period cannot accidentally fall through to the monthly calculation.
    if period not in ("weekly", "monthly"):
        raise ValueError("period must be weekly or monthly.")

    # Store totals under the starting date of each week or month.
    # Using a complete date keeps different years and their months distinct.
    period_counts = {}

    for sighting in sightings:
        # Parse the source timestamp and extract its calendar date. Clock time
        # does not affect which week or month the sighting belongs to.
        # Use the date as written in the record, without timezone conversion.
        sighting_date = datetime.fromisoformat(sighting["date"]).date()

        if period == "weekly":
            # weekday() returns Monday=0 through Sunday=6. Subtract that many
            # days to find Monday: a Monday stays as it is, while a Sunday
            # moves back six days. Every date in that week gets the same key.
            # This also keeps a week together when it crosses a year boundary.
            period_start = sighting_date - timedelta(
                days=sighting_date.weekday()
            )
        else:
            # Keep the sighting's year and month, but use day 1 as the key.
            # Every date in that calendar month now shares the same group,
            # while the same month in a different year remains separate.
            period_start = sighting_date.replace(day=1)

        # Turn the group key into a YYYY-MM-DD string suitable for JSON.
        # Then add this sighting to that week's or month's running total.
        label = period_start.isoformat()
        period_counts[label] = period_counts.get(label, 0) + 1

    # These ISO date strings sort in chronological order, so the returned
    # report runs from oldest to newest even if the input records are shuffled.
    # We include only groups encountered above, without adding empty periods.
    report = []

    for label in sorted(period_counts):
        report.append({
            "period_start": label,
            "count": period_counts[label],
        })

    # Location and date filters were applied before this function was called.
    # A group's start label may precede the requested start_date, but its total
    # includes only the matching sightings supplied to this calculation.
    return report
