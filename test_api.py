"""Test API error handling, location filtering and date-range filtering.

TestClient sends requests directly to our FastAPI application in this Python
process, so a separate Uvicorn server is unnecessary for these checks.

patch temporarily replaces main.httpx.get with a simulated result or exception.
This lets us exercise the real endpoints and their processing logic without
depending on Elanco's availability or on changes to its live dataset.
"""

# unittest groups the tests and supplies assertions. patch temporarily replaces
# the outgoing GET used in main.py; the original function is restored when its
# with block ends, so one simulated scenario does not leak into the next.
import unittest
from unittest.mock import patch

# HTTPX provides the fake response objects and simulated network exceptions.
# TestClient exercises our application's routing, validation and JSON responses.
import httpx
from fastapi.testclient import TestClient

# Use the real application, including the endpoints and shared loading helper
# defined in main.py, rather than building a separate application for the tests.
from main import app


class TestAPIErrors(unittest.TestCase):
    """Check how upstream failures are explained to callers of our API."""

    def test_timeout_returns_504(self):
        """Translate an Elanco read timeout into the expected HTTP 504 response."""
        client = TestClient(app)

        # side_effect makes the replaced GET raise this exception when called.
        # The endpoint must handle it and return an error response rather than
        # letting the request crash with an unhandled exception.
        with patch(
            "main.httpx.get",
            side_effect=httpx.ReadTimeout("Simulated timeout"),
        ):
            response = client.get("/sightings")

        # Check both the status code and the explanation sent to the caller.
        # HTTP 504 identifies the timeout while detail explains it in plain text.
        self.assertEqual(response.status_code, 504)
        self.assertEqual(
            response.json()["detail"],
            "Elanco's API took too long to respond.",
        )

    def test_connection_failure_returns_502(self):
        """Translate a failed connection to Elanco into the expected HTTP 502."""
        client = TestClient(app)

        # Simulate a connection problem independently of the timeout scenario.
        # This exercises main.py's general HTTP-error handler.
        with patch(
            "main.httpx.get",
            side_effect=httpx.ConnectError("Simulated connection failure"),
        ):
            response = client.get("/sightings")

        # Our API should explain that retrieving upstream data failed.
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Could not retrieve data from Elanco.",
        )

    def test_bad_responses_return_502(self):
        """Reject unsuccessful responses, invalid JSON and a wrong JSON shape."""
        client = TestClient(app)

        # Attach a request to each fake response so HTTPX's raise_for_status()
        # works when main.py checks it. Creating this Request does not send it.
        request = httpx.Request(
            "GET",
            "https://dev-task.elancoapps.com/data/tick-sightings",
        )

        # Each case pairs a simulated upstream response with the explanation
        # our own API should return. A successful status alone is not enough:
        # the response body must also contain valid JSON in the expected shape.
        cases = [
            (
                # Elanco reports an unsuccessful HTTP status. Our API should
                # translate the upstream failure into its own HTTP 502 response.
                httpx.Response(503, request=request),
                "Could not retrieve data from Elanco.",
            ),
            (
                # HTTP 200 indicates success, but these raw response bytes
                # cannot be decoded as JSON.
                httpx.Response(200, content=b"not JSON", request=request),
                "Elanco returned invalid JSON.",
            ),
            (
                # This body is valid JSON, but it is an object rather than
                # the list of sighting records our processing expects.
                httpx.Response(
                    200, json={"unexpected": "data"}, request=request
                ),
                "Elanco returned an unexpected data format.",
            ),
        ]

        for fake_response, expected_message in cases:
            # Label each scenario so test output identifies which case failed.
            # subTest also lets unittest continue checking the other cases
            # after an assertion failure in one of them.
            with self.subTest(expected=expected_message):
                # return_value supplies the fake response instead of raising
                # a network exception or contacting the real upstream API.
                with patch("main.httpx.get", return_value=fake_response):
                    response = client.get("/sightings")

                self.assertEqual(response.status_code, 502)
                self.assertEqual(
                    response.json()["detail"],
                    expected_message,
                )


class TestLocationFiltering(unittest.TestCase):
    """Check location matching through the actual sighting-list endpoint."""

    def test_location_filter_ignores_case_and_spaces(self):
        """Match London despite surrounding whitespace and mixed capitals."""
        client = TestClient(app)

        # Supply two valid sightings in different cities. A London query must
        # keep the first record and exclude Manchester.
        records = [
            {"id": "1", "date": "2024-06-15T12:00:00", "location": "London"},
            {"id": "2", "date": "2024-06-15T12:00:00", "location": "Manchester"},
        ]

        # json=records creates a response body containing our controlled data.
        # example.test is just a label for this fake request; it is not visited.
        upstream_response = httpx.Response(
            200,
            json=records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        with patch("main.httpx.get", return_value=upstream_response):
            # params supplies URL query parameters. Deliberately mix capitals
            # and surrounding whitespace to check the location-normalisation rule.
            response = client.get(
                "/sightings",
                params={"location": "  lOnDoN  "},
            )

        self.assertEqual(response.status_code, 200)

        # received describes the original two-record batch. count and sightings
        # describe only the one record matching the caller's location filter.
        result = response.json()
        self.assertEqual(result["received"], 2)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sightings"], [records[0]])


class TestDateFiltering(unittest.TestCase):
    """Check inclusive date limits and rejection of unusable date inputs."""

    def test_date_range_includes_both_boundary_days(self):
        """Include both boundary days while applying the location filter too."""
        client = TestClient(app)

        # Place records just before, exactly on and just after the chosen
        # calendar-year boundaries. The late-night end-date record checks that
        # the entire final day is included, rather than only its midnight.
        # Manchester is inside the date range but must fail the London filter.
        records = [
            {"id": "before", "date": "2023-12-31T23:59:59", "location": "London"},
            {"id": "start", "date": "2024-01-01T00:00:00", "location": "London"},
            {"id": "end", "date": "2024-12-31T23:59:59", "location": "London"},
            {"id": "after", "date": "2025-01-01T00:00:00", "location": "London"},
            {"id": "other", "date": "2024-06-15T12:00:00", "location": "Manchester"},
        ]

        upstream_response = httpx.Response(
            200,
            json=records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        # Request London sightings during 2024 through the same query parameters
        # a browser or another application would send to our API.
        with patch("main.httpx.get", return_value=upstream_response):
            response = client.get(
                "/sightings",
                params={
                    "location": "London",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                },
            )

        self.assertEqual(response.status_code, 200)

        # Five records arrived from the simulated source. Only the two London
        # records on the boundary days should remain in the returned list.
        # Checking the actual records also checks that before/after dates and
        # the other city were excluded, not just that the final number is two.
        result = response.json()
        self.assertEqual(result["received"], 5)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["sightings"], [records[1], records[2]])

    def test_invalid_date_inputs_return_422(self):
        """Reject reversed ranges, impossible dates and text that is not a date."""
        client = TestClient(app)

        # The reversed range is checked by load_sightings in main.py.
        # FastAPI checks the date input format and calendar validity before
        # the endpoint runs, including rejecting 30 February.
        cases = [
            {"start_date": "2024-12-31", "end_date": "2024-01-01"},
            {"start_date": "2024-02-30"},
            {"end_date": "not-a-date"},
        ]

        for params in cases:
            with self.subTest(params=params):
                # Retain the mock as mocked_get so we can inspect whether
                # the application tried to fetch upstream data in this case.
                with patch("main.httpx.get") as mocked_get:
                    response = client.get("/sightings", params=params)

                # HTTP 422 asks the caller to correct their input.
                # No outgoing GET should be needed for an invalid request,
                # so also check that rejection happened before fetching data.
                self.assertEqual(response.status_code, 422)
                mocked_get.assert_not_called()
