"""HTTP entry point for the Elanco Tick Tracker backend.

This file receives requests, retrieves Elanco's data and returns JSON responses.
It connects the two helper modules: data_processing cleans and filters records,
while reporting calculates regional totals and trends over time.

Each data or report request follows the same flow:
fetch the source data -> remove unusable records and duplicate IDs ->
apply the requested filters -> return sightings or calculate a report.
"""

# These built-in types describe the inputs accepted by our endpoints.
# date represents a calendar date; None means that a filter was not supplied.
# Literal declares the two period choices that FastAPI will accept for trends.
from datetime import date
from typing import Literal

# HTTPX sends requests to Elanco's external API. FastAPI receives requests to
# our own API, and HTTPException returns a clear error response to the caller.
import httpx
from fastapi import FastAPI, HTTPException

# Keep record-cleaning and reporting rules in their own modules so all
# endpoints can reuse the same rules and those rules can be tested separately.
from data_processing import filter_by_date, filter_by_location, process_sightings
from reporting import count_by_period, count_by_region

# Create the web API. This title appears in its interactive documentation,
# which FastAPI makes available at /docs when the server is running.
app = FastAPI(title="Elanco Tick Tracker")


@app.get("/")
def home():
    """Return a simple message showing that our application can respond.

    This does not fetch sighting data or check whether Elanco's API is available.
    """
    return {"message": "Elanco Tick Tracker API is running"}


def load_sightings(
    location: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Fetch, clean and filter a batch of sightings for any data endpoint.

    The endpoint functions below pass their query parameters into this helper.
    Sharing this flow makes sighting lists and reports use the same cleaning,
    filtering and upstream error-handling rules.

    The returned dictionary contains matching sightings, their count and
    counters describing the original batch and the records removed from it.
    """
    # FastAPI checks the format of date query parameters at the endpoints.
    # Here we check their relationship: a start date cannot follow an end date.
    # Reject this request before contacting Elanco because the range is unusable.
    # HTTP 422 tells the caller to correct the input they supplied.
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date.",
        )

    # Retrieve a fresh batch from Elanco for this request. HTTPX's timeout
    # limits how long individual network operations can wait; it is not a
    # guaranteed 20-second deadline for the entire request.
    try:
        response = httpx.get(
            "https://dev-task.elancoapps.com/data/tick-sightings",
            timeout=20.0,
        )

        # Check for an unsuccessful HTTP status before trying to use the body.
        # Then decode the response's JSON into Python lists/dictionaries.
        response.raise_for_status()
        sightings = response.json()

    # Handle timeouts before the broader HTTPError handler below because
    # HTTPX timeout exceptions are also HTTP errors. HTTP 504 tells the caller
    # that our request to the upstream service took too long.
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Elanco's API took too long to respond.",
        )

    # Connection problems and unsuccessful upstream HTTP responses reach this
    # handler. HTTP 502 explains that we could not obtain usable data from
    # Elanco, supporting the task's requirement to handle API failures clearly.
    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve data from Elanco.",
        )

    # A response may arrive successfully but contain a body that is not valid
    # JSON. Report an upstream-data problem instead of trying to process it.
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Elanco returned invalid JSON.",
        )

    # Valid JSON can still have the wrong structure, such as an object instead
    # of a list of records. Require the expected outer structure here; the
    # processing module checks the individual records inside that list.
    if not isinstance(sightings, list):
        raise HTTPException(
            status_code=502,
            detail="Elanco returned an unexpected data format.",
        )

    # Clean the whole batch before applying search filters. process_sightings
    # removes records that fail validation and repeated valid IDs, and records
    # how many were removed. This prevents unusable or duplicate reports from
    # inflating the sighting list and the regional or time-based totals.
    processed = process_sightings(sightings)

    # Apply location and date filters to the cleaned records. A filter left as
    # None places no restriction on that field. The processing module contains
    # the matching rules, including inclusive start and end calendar dates.
    # Filtering before reporting ensures that reports describe the chosen
    # location/date range rather than the entire upstream dataset.
    filtered = filter_by_location(processed["sightings"], location)
    filtered = filter_by_date(filtered, start_date, end_date)

    # Replace the sighting list with its matching records and update count.
    # received remains the original batch size; invalid_removed and
    # duplicates_removed describe cleaning across that whole batch.
    # count describes only the valid, unique records matching this request.
    processed["sightings"] = filtered
    processed["count"] = len(filtered)

    return processed


# FastAPI turns the arguments below into optional URL query parameters.
# For example: /sightings?location=London&start_date=2024-01-01
# Date values use YYYY-MM-DD; invalid date inputs receive an HTTP 422 response.
@app.get("/sightings")
def get_sightings(
    location: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Return cleaned sightings, optionally filtered by location and date.

    This is the task's search/filtering endpoint. It returns individual
    records, their matching count and the source-data cleaning counters.
    """
    return load_sightings(location, start_date, end_date)


@app.get("/reports/regions")
def get_regional_counts(
    location: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Return the number of matching sightings grouped by region.

    The source records contain city names. The reporting module uses its
    city-to-region mapping to produce the regional totals required by the task.
    """
    # Reuse the common pipeline so the regional report respects the same
    # filters, duplicate removal and validation as the individual sighting list.
    processed = load_sightings(location, start_date, end_date)

    # Return regional totals alongside the source-data cleaning counters.
    # count is the total number of matching sightings, not the number of regions.
    return {
        "received": processed["received"],
        "count": processed["count"],
        "invalid_removed": processed["invalid_removed"],
        "duplicates_removed": processed["duplicates_removed"],
        "regions": count_by_region(processed["sightings"]),
    }


@app.get("/reports/trends")
def get_trends(
    period: Literal["weekly", "monthly"] = "monthly",
    location: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Return matching sighting totals grouped into weeks or months.

    Choose period=weekly or period=monthly; leaving it out selects monthly.
    Weekly groups start on Monday and monthly groups on the first of the month.
    Only periods containing matching sightings appear in the report.
    """
    # Literal lets FastAPI reject unsupported periods, such as "daily",
    # with HTTP 422 before this function contacts Elanco. For accepted inputs,
    # retrieve and filter the data through the same shared pipeline.
    processed = load_sightings(location, start_date, end_date)

    # The reporting helper groups the matching records and puts the periods
    # in date order. This provides the task's trends-over-time insight.
    # Each period_start labels the whole group: it may precede start_date
    # when the chosen range begins partway through a week or month, but only
    # sightings inside the requested range contribute to that group's count.
    return {
        "received": processed["received"],
        "count": processed["count"],
        "invalid_removed": processed["invalid_removed"],
        "duplicates_removed": processed["duplicates_removed"],
        "period": period,
        "trends": count_by_period(processed["sightings"], period),
    }
