from datetime import datetime, timedelta
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

    
class TestTrendReports(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.records = [
            {"id": "1", "date": "2025-01-06T00:00:00", "location": "London"},
            {"id": "2", "date": "2025-01-05T23:59:59", "location": "London"},
            {"id": "3", "date": "2024-12-30T00:00:00", "location": "London"},
            {"id": "4", "date": "2024-12-29T23:59:59", "location": "London"},
            {"id": "5", "date": "2025-01-04T12:00:00", "location": "Manchester"},
            {"id": "bad", "date": "not-a-date", "location": "London"},
        ]
        self.records.append(self.records[0].copy())

    def get_report(self, params):
        upstream_response = httpx.Response(
            200,
            json=self.records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        with patch("main.httpx.get", return_value=upstream_response):
            return self.client.get("/reports/trends", params=params)

    def test_weekly_and_monthly_boundaries(self):
        cases = {
            "weekly": [
                {"period_start": "2024-12-23", "count": 1},
                {"period_start": "2024-12-30", "count": 3},
                {"period_start": "2025-01-06", "count": 1},
            ],
            "monthly": [
                {"period_start": "2024-12-01", "count": 2},
                {"period_start": "2025-01-01", "count": 3},
            ],
        }

        for period, expected in cases.items():
            with self.subTest(period=period):
                response = self.get_report({"period": period})

                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(result["received"], 7)
                self.assertEqual(result["count"], 5)
                self.assertEqual(result["invalid_removed"], 1)
                self.assertEqual(result["duplicates_removed"], 1)
                self.assertEqual(result["trends"], expected)

    def test_location_and_date_filters(self):
        response = self.get_report({
            "period": "weekly",
            "location": "  lOnDoN  ",
            "start_date": "2024-12-30",
            "end_date": "2025-01-05",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(
            response.json()["trends"],
            [{"period_start": "2024-12-30", "count": 2}],
        )

    def test_no_matches_returns_empty_monthly_report(self):
        response = self.get_report({"start_date": "2026-01-01"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["period"], "monthly")
        self.assertEqual(response.json()["trends"], [])

    def test_invalid_inputs_return_422_without_fetching(self):
        cases = [
            {"period": "daily"},
            {"period": "monthly", "start_date": "not-a-date"},
            {
                "period": "weekly",
                "start_date": "2025-01-06",
                "end_date": "2024-12-29",
            },
        ]

        for params in cases:
            with self.subTest(params=params):
                with patch("main.httpx.get") as mocked_get:
                    response = self.client.get("/reports/trends", params=params)

                self.assertEqual(response.status_code, 422)
                mocked_get.assert_not_called()