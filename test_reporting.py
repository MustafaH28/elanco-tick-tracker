import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from main import app


class TestRegionalReport(unittest.TestCase):
    def test_regions_use_clean_data_and_keep_unknown_cities(self):
        client = TestClient(app)

        records = [
            {
                "id": "1",
                "date": "2024-06-15T12:00:00",
                "location": "  mAnChEsTeR  ",
            },
            {
                "id": "2",
                "date": "2024-06-15T12:00:00",
                "location": "Liverpool",
            },
            {
                "id": "3",
                "date": "2024-06-15T12:00:00",
                "location": "Unmapped town",
            },
            {
                "id": "4",
                "date": "not-a-date",
                "location": "London",
            },
        ]

        records.append(records[0].copy())

        upstream_response = httpx.Response(
            200,
            json=records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        with patch("main.httpx.get", return_value=upstream_response):
            response = client.get("/reports/regions")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "received": 5,
                "count": 3,
                "invalid_removed": 1,
                "duplicates_removed": 1,
                "regions": [
                    {"region": "North West", "count": 2},
                    {"region": "Unknown", "count": 1},
                ],
            },
        )
