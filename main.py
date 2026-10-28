from data_processing import process_sightings
import httpx
from fastapi import FastAPI

app = FastAPI(title="Elanco Tick Tracker")


@app.get("/")
def home():
    return {"message": "Elanco Tick Tracker API is running"}
@app.get("/sightings")

def get_sightings():
    response = httpx.get(
        "https://dev-task.elancoapps.com/data/tick-sightings",
        timeout=20.0,
    )
    response.raise_for_status()
    sightings = response.json()
    return process_sightings(sightings)