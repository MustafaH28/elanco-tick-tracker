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