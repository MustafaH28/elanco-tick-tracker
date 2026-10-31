# Elanco Tick Tracker API

**Author: Mustafa Hassan**

A Python backend built for the Elanco Software Engineer Placement technical task. It retrieves the provided tick-sighting data, removes unusable and duplicate records, supports location/date searches, and returns regional counts and weekly or monthly trends.

Data source: [Elanco tick-sightings API](https://dev-task.elancoapps.com/data/tick-sightings).

## Video walkthrough

[Download the captioned walkthrough (MP4, 6 minutes 17 seconds)](docs/Elanco_Tick_Tracker_Walkthrough.mp4?raw=true)

The walkthrough is in 1080p and uses on-screen captions. It covers the code structure, data cleaning, location/date filtering, regional counts, weekly/monthly trends, error handling, automated tests and the larger-dataset strategy.

[Optional subtitle file (SRT)](docs/Elanco_Tick_Tracker_Captions.srt?raw=true)

## Features

- Clean source records and report how many invalid records and duplicate IDs were removed.
- Filter sightings by location and an inclusive calendar-date range.
- Count matching sightings by region, retaining unmapped cities under `Unknown`.
- Group matching sightings into Monday-to-Sunday weeks or calendar months.
- Return clear errors for invalid query inputs and upstream failures.
- Explore and run requests through FastAPI's interactive documentation.

## Technology and choices

| Component | Purpose |
| --- | --- |
| Python | Data validation, filtering and aggregation using straightforward functions. |
| FastAPI | HTTP endpoints, query-parameter validation and generated API documentation. |
| HTTPX | Requests to Elanco, with explicit timeouts and error handling. |
| Uvicorn | Runs the FastAPI application locally. |
| `unittest`, `unittest.mock` and `TestClient` | Repeatable checks using controlled upstream responses. |

The development environment is Windows with Python 3.14.6. Use Python 3.14 to reproduce it. `requirements.txt` records exact installed package versions, including FastAPI 0.162.0, HTTPX 0.28.1 and Uvicorn 0.54.0, plus supporting dependencies.

The MVP keeps the request flow synchronous and processes each downloaded batch in memory. Separate processing and reporting modules keep the rules reusable and easy to test. There is no database, scheduled ingestion or cache in this version.

## Run locally

Download or clone the repository, then open a terminal in its root folder, which contains `main.py` and `requirements.txt`. Internet access is required to install dependencies and retrieve live sightings.

### Windows

Check that your Python command selects Python 3.14:

```powershell
python --version
```

Create an isolated environment for the project's packages:

```powershell
python -m venv .venv
```

Install the recorded dependencies and check their compatibility:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Start the API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

These commands use the environment's Python directly, so activating it through a PowerShell script is unnecessary. `--reload` restarts the application when development files change. Stop the server with **Ctrl+C**.

### macOS / Linux

With Python 3.14 installed, the equivalent commands are:

```bash
python3.14 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip check
./.venv/bin/python -m uvicorn main:app --reload
```

### Open the application

- [Running-status message](http://127.0.0.1:8000/)
- [Interactive API documentation](http://127.0.0.1:8000/docs)

In the documentation, expand an endpoint, select **Try it out**, enter any filters and select **Execute**. The root message confirms that this application can respond; it does not check Elanco's availability.

## Endpoints

| Method | Path | Returns | Optional query parameters |
| --- | --- | --- | --- |
| GET | `/` | Application running-status message. | None |
| GET | `/sightings` | Cleaned, matching sighting records and counts. | `location`, `start_date`, `end_date` |
| GET | `/reports/regions` | Matching sighting totals grouped by region. | `location`, `start_date`, `end_date` |
| GET | `/reports/trends` | Matching sighting totals grouped by week or month. | `period`, `location`, `start_date`, `end_date` |

Examples:

- [All cleaned sightings](http://127.0.0.1:8000/sightings)
- [London sightings during 2024](http://127.0.0.1:8000/sightings?location=London&start_date=2024-01-01&end_date=2024-12-31)
- [Regional counts during 2024](http://127.0.0.1:8000/reports/regions?start_date=2024-01-01&end_date=2024-12-31)
- [Monthly London trends during 2024](http://127.0.0.1:8000/reports/trends?period=monthly&location=London&start_date=2024-01-01&end_date=2024-12-31)
- [Weekly London trends during 2024](http://127.0.0.1:8000/reports/trends?period=weekly&location=London&start_date=2024-01-01&end_date=2024-12-31)

### Query rules

| Parameter | Behaviour |
| --- | --- |
| `location` | Exact city-name match, ignoring capitalisation and surrounding whitespace. Omit it to include all cities. A blank value matches no validated locations. |
| `start_date` | Optional lower limit in `YYYY-MM-DD` form. Includes the entire start day. |
| `end_date` | Optional upper limit in `YYYY-MM-DD` form. Includes the entire end day. |
| `period` | `weekly` or `monthly`, used only by `/reports/trends`. Defaults to `monthly`. |

Either date limit can be used on its own. Source timestamps are compared and grouped using their written calendar date, without timezone conversion. A reversed range, invalid calendar date or unsupported period returns HTTP 422.

Weekly labels are the Monday starting that week. Monthly labels are the first day of the month. A label may precede the requested start date when the range begins partway through a period; only records inside the requested range contribute to its count. Groups without matching sightings are omitted. Valid queries with no matches return HTTP 200, a count of zero and an empty result list.

## Data handling and response counts

Each data/report request uses the same `load_sightings` flow:

1. Fetch a fresh response from Elanco and check the HTTP status, JSON decoding and outer list structure.
2. Validate the individual records and keep the first valid occurrence of each exact ID.
3. Apply any location and date limits to the cleaned records.
4. Return those records or calculate the requested report from them.

| Source field | Validation / use |
| --- | --- |
| `id` | Required non-empty string. Used for exact, case-sensitive duplicate detection. IDs are not trimmed or rewritten. |
| `date` | Required non-empty string that `datetime.fromisoformat` can parse. Used for date filtering and time grouping. |
| `location` | Required non-empty string. Used for location matching and regional mapping. |
| `species`, `latinName` | Optional for the implemented filters and reports; retained when supplied. |

Non-dictionary records, missing required values, whitespace-only required values and unreadable dates are removed. Validation happens before duplicate checking, so an invalid record cannot prevent a later valid record with that ID from being accepted. These checks establish whether a record is usable; they do not verify the real-world accuracy of a sighting.

The response counters have different purposes:

| Field | Meaning |
| --- | --- |
| `received` | Number of records in the original upstream batch. |
| `invalid_removed` | Unusable records removed from that entire batch. |
| `duplicates_removed` | Later valid occurrences of already accepted IDs removed from that entire batch. |
| `count` | Number of valid, unique sightings remaining after the requested filters. For reports, this counts sightings, not groups. |

`/sightings` includes a `sightings` list. The reporting endpoints replace that list with `regions` or `trends`; the trend response also identifies `period`. Filtering does not change the source-batch counters.

### Regional mapping

The source supplies city names rather than a region field. `CITY_TO_REGION` in `reporting.py` explicitly maps the known cities to reporting groups: English regions plus Scotland and Wales. Manchester and Liverpool, for example, both count towards North West.

`Newcastle` is assumed to mean Newcastle upon Tyne. A city without a mapping remains in an `Unknown` group so its sighting is not silently lost. The lookup needs extending when new cities are introduced. Regional results are sorted alphabetically; trends are sorted chronologically.

## Error handling

| Status | Situation |
| --- | --- |
| 422 | Invalid query date, reversed range or unsupported trend period. Rejected before fetching source data. |
| 502 | Upstream connection/HTTP failure, invalid JSON or a JSON response whose outer structure is not a list. |
| 504 | An upstream network operation times out. |

HTTPX is configured with `timeout=20.0`. This limits individual network operations rather than imposing a guaranteed 20-second deadline on the whole request. Error responses include a `detail` explanation. Invalid individual records inside an otherwise valid list are removed and counted instead of failing the entire batch.

## Tests

Run the suite from the repository root.

Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest test_processing test_api test_reporting -v
```

macOS / Linux:

```bash
./.venv/bin/python -m unittest test_processing test_api test_reporting -v
```

The suite contains **12 test methods**, with additional cases checked through subtests. Expected successful output includes `Ran 12 tests` and `OK`.

- `test_processing.py`: an invalid date and duplicate record are removed, with correct kept records and counters.
- `test_api.py`: timeouts, connection failures, unsuccessful statuses, bad JSON, wrong outer structure, location matching, inclusive date boundaries and invalid date inputs.
- `test_reporting.py`: regional grouping and unknown cities, cleanup before aggregation, weekly/monthly boundaries across New Year, combined filters, default monthly/empty results and rejection before upstream fetching.

API tests replace `main.httpx.get` with controlled responses or exceptions. They can run without contacting Elanco after dependencies are installed. Live requests remain useful for checking connectivity and the current source response.

## Project files

| File | Responsibility |
| --- | --- |
| `main.py` | Endpoints, shared retrieval/processing flow and API error responses. |
| `data_processing.py` | Record validation, duplicate removal and filtering. |
| `reporting.py` | City-to-region lookup, regional totals and time grouping. |
| `test_processing.py` | Processing checks. |
| `test_api.py` | API failure and filtering checks. |
| `test_reporting.py` | Regional and trend-report checks. |
| `requirements.txt` | Recorded package versions. |
| `.gitignore` | Excludes the virtual environment, Python cache files and local environment settings. |
| `README.md` | Project choices, setup, usage and larger-dataset plan. |

## Larger-dataset strategy

The supplied snapshot examined during development contained 1,000 records. The current implementation downloads and parses a full response for every data/report request, then processes it in memory. It has no upstream batching, response pagination, persistent storage or caching, so its memory use and repeated download costs would become a limitation as the source grows.

For `n` input records, cleaning uses one pass with an ID set for expected fast membership checks; the location/date passes are also linear. Regional grouping takes O(n + r log r) for `r` output regions, and time grouping takes O(n + p log p) for `p` occupied periods, including sorting. Memory use grows as O(n). These are complexity estimates from the implementation, not large-scale benchmark results.

For a larger deployment, I would develop the ingestion and query paths in stages:

1. **Separate ingestion from requests.** Refresh source data in a background job and serve a stored, validated snapshot. Record refresh time and expose freshness clearly if a last-successful snapshot is used during an upstream outage.
2. **Bound ingestion work.** Use upstream pagination or incremental updates if available. Otherwise investigate streamed downloading and incremental JSON parsing; adding pagination only to our output would not remove the current full upstream download.
3. **Persist and index records.** Store sightings with a unique ID constraint and indexes for location/date queries. Define how corrections to an existing ID are handled, rather than assuming every repeated ID is always an unwanted duplicate.
4. **Filter and aggregate in storage.** Retrieve only the matching records, paginate sighting lists and cache commonly requested reports with keys that include every filter and the chosen period.
5. **Monitor the pipeline.** Track ingestion failures, latency, invalid/duplicate counts and unmapped cities. Add bounded retries with backoff for transient upstream failures, plus tests using larger and more varied batches.

These are planned improvements, not features claimed by the current MVP. Other future work includes broader location mapping, timezone normalisation if the source begins mixing timezone offsets, and automated checks for new dataset shapes. The optional AI/ML extension is outside this implementation.

## Documentation references

- [FastAPI: first steps and interactive documentation](https://fastapi.tiangolo.com/tutorial/first-steps/)
- [HTTPX: timeout behaviour](https://www.python-httpx.org/advanced/timeouts/)
- [pip freeze: recorded package versions](https://pip.pypa.io/en/stable/cli/pip_freeze/)
- [pip check: installed dependency compatibility](https://pip.pypa.io/en/stable/cli/pip_check/)

