import httpx
from fastapi import FastAPI, HTTPException

from data_processing import filter_by_location, process_sightings

app = FastAPI(title="Elanco Tick Tracker")


@app.get("/")
def home():
    return {"message": "Elanco Tick Tracker API is running"}


@app.get("/sightings")
def get_sightings(location: str | None = None):
    try:
        response = httpx.get(
            "https://dev-task.elancoapps.com/data/tick-sightings",
            timeout=20.0,
        )
        response.raise_for_status()
        sightings = response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Elanco's API took too long to respond.",
        )

    except httpx.HTTPError:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve data from Elanco.",
        )

    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Elanco returned invalid JSON.",
        )

    if not isinstance(sightings, list):
        raise HTTPException(
            status_code=502,
            detail="Elanco returned an unexpected data format.",
        )

    processed = process_sightings(sightings)
    filtered = filter_by_location(processed["sightings"], location)

    processed["sightings"] = filtered
    processed["count"] = len(filtered)

    return processed