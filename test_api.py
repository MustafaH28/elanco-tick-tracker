import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from main import app


class TestAPIErrors(unittest.TestCase):
    def test_timeout_returns_504(self):
        client = TestClient(app)

        with patch(
            "main.httpx.get",
            side_effect=httpx.ReadTimeout("Simulated timeout"),
        ):
            response = client.get("/sightings")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(
            response.json()["detail"],
            "Elanco's API took too long to respond.",
        )
    
    def test_connection_failure_returns_502(self):
        client = TestClient(app)

        with patch(
            "main.httpx.get",
            side_effect=httpx.ConnectError("Simulated connection failure"),
        ):
            response = client.get("/sightings")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Could not retrieve data from Elanco.",
        )

    def test_bad_responses_return_502(self):
        client = TestClient(app)
        request = httpx.Request(
            "GET",
            "https://dev-task.elancoapps.com/data/tick-sightings",
        )

        cases = [
            (
                httpx.Response(503, request=request),
                "Could not retrieve data from Elanco.",
            ),
            (
                httpx.Response(200, content=b"not JSON", request=request),
                "Elanco returned invalid JSON.",
            ),
            (
                httpx.Response(
                    200, json={"unexpected": "data"}, request=request
                ),
                "Elanco returned an unexpected data format.",
            ),
        ]

        for fake_response, expected_message in cases:
            with self.subTest(expected=expected_message):
                with patch("main.httpx.get", return_value=fake_response):
                    response = client.get("/sightings")

                self.assertEqual(response.status_code, 502)
                self.assertEqual(
                    response.json()["detail"],
                    expected_message,
                )
class TestLocationFiltering(unittest.TestCase):
    def test_location_filter_ignores_case_and_spaces(self):
        client = TestClient(app)

        records = [
            {"id": "1", "date": "2024-06-15T12:00:00", "location": "London"},
            {"id": "2", "date": "2024-06-15T12:00:00", "location": "Manchester"},
        ]

        upstream_response = httpx.Response(
            200,
            json=records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        with patch("main.httpx.get", return_value=upstream_response):
            response = client.get(
                "/sightings",
                params={"location": "  lOnDoN  "},
            )

        self.assertEqual(response.status_code, 200)

        result = response.json()
        self.assertEqual(result["received"], 2)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sightings"], [records[0]])

class TestDateFiltering(unittest.TestCase):

    def test_date_range_includes_both_boundary_days(self):
        client = TestClient(app)

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

        result = response.json()
        self.assertEqual(result["received"], 5)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["sightings"], [records[1], records[2]])

    def test_invalid_date_inputs_return_422(self):
        client = TestClient(app)

        cases = [
            {"start_date": "2024-12-31", "end_date": "2024-01-01"},
            {"start_date": "2024-02-30"},
            {"end_date": "not-a-date"},
        ]

        for params in cases:
            with self.subTest(params=params):
                with patch("main.httpx.get") as mocked_get:
                    response = client.get("/sightings", params=params)

                self.assertEqual(response.status_code, 422)
                mocked_get.assert_not_called()


      