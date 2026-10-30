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