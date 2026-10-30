from datetime import datetime, timedelta

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
    region_counts = {}

    for sighting in sightings:
        city = sighting["location"].strip().casefold()
        region = CITY_TO_REGION.get(city, "Unknown")
        region_counts[region] = region_counts.get(region, 0) + 1

    report = []

    for region in sorted(region_counts):
        report.append({
            "region": region,
            "count": region_counts[region],
        })

    return report

def count_by_period(sightings, period):
    if period not in ("weekly", "monthly"):
        raise ValueError("period must be weekly or monthly.")

    period_counts = {}

    for sighting in sightings:
        sighting_date = datetime.fromisoformat(sighting["date"]).date()

        if period == "weekly":
            period_start = sighting_date - timedelta(
                days=sighting_date.weekday()
            )
        else:
            period_start = sighting_date.replace(day=1)

        label = period_start.isoformat()
        period_counts[label] = period_counts.get(label, 0) + 1

    report = []

    for label in sorted(period_counts):
        report.append({
            "period_start": label,
            "count": period_counts[label],
        })

    return report