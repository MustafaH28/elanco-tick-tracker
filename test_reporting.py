"""Test the regional and weekly/monthly reporting endpoints.

These checks send requests to the real FastAPI application through TestClient.
Simulated Elanco responses provide controlled records, so expected counts are
repeatable and the tests do not depend on the live API or a running web server.

Together they check that reports use cleaned data, retain unmapped locations,
group dates correctly and apply the same location/date filters as /sightings.
"""

# unittest provides the test framework and assertions. patch temporarily replaces
# main.httpx.get so each test can choose the data returned by the upstream API.
import unittest
from unittest.mock import patch

# HTTPX builds the simulated responses. TestClient calls our application
# directly, including its routing, input validation and report calculations.
import httpx
from fastapi.testclient import TestClient

from main import app


class TestRegionalReport(unittest.TestCase):
    """Check that regional totals use valid, unique sightings without losing cities."""

    def test_regions_use_clean_data_and_keep_unknown_cities(self):
        """Group known cities, keep an unknown city and check cleanup counters."""
        client = TestClient(app)

        # Manchester and Liverpool should both contribute to North West.
        # Mixed capitalisation and surrounding whitespace in Manchester also
        # check that the city-to-region lookup normalises the source location.
        # Unmapped town should remain in an explicit Unknown group.
        # London's invalid date should prevent that record from being counted.
        records = [
            {
                "id": "1",
                "date": "2024-06-15T12:00:00",
                "location": "  mAnChEsTeR  ",
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

        # Add a fifth record with the same ID and values as Manchester.
        # It should be removed as a duplicate instead of increasing its total.
        records.append(records[0].copy())

        # Build a successful upstream response containing these five records.
        # The attached Request supports HTTPX status checking; neither creating
        # these objects nor using example.test sends an external request.
        upstream_response = httpx.Response(
            200,
            json=records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        # Exercise the actual regional endpoint while supplying our fake batch.
        with patch("main.httpx.get", return_value=upstream_response):
            response = client.get("/reports/regions")

        self.assertEqual(response.status_code, 200)

        # Compare the complete JSON payload with the expected result:
        # five received - one invalid - one duplicate = three kept sightings.
        # The two known cities share North West; the unmapped city remains
        # counted under Unknown. The regional list is also in alphabetical order.
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
    """Check time grouping, report filters, empty results and invalid inputs."""

    def setUp(self):
        """Prepare a fresh client and sample batch before each test method."""
        self.client = TestClient(app)

        # The valid dates deliberately arrive out of chronological order.
        # They cover Sunday/Monday boundaries and a week crossing New Year:
        # 29 December is Sunday; 30 December and 6 January are Mondays.
        # Manchester provides a record inside the later date-filter window
        # that should be excluded when a test requests London specifically.
        self.records = [
            {"id": "1", "date": "2025-01-06T00:00:00", "location": "London"},
            {"id": "2", "date": "2025-01-05T23:59:59", "location": "London"},
            {"id": "3", "date": "2024-12-30T00:00:00", "location": "London"},
            {"id": "4", "date": "2024-12-29T23:59:59", "location": "London"},
            {"id": "5", "date": "2025-01-04T12:00:00", "location": "Manchester"},
            {"id": "bad", "date": "not-a-date", "location": "London"},
        ]

        # Add a duplicate to make seven source records in total.
        # Removing that duplicate and the bad date should leave five valid,
        # unique sightings before any location or date filters are applied.
        self.records.append(self.records[0].copy())

    def get_report(self, params):
        """Request a trend report using our sample data and chosen query inputs."""
        # This is a test helper, not another reporting calculation. It supplies
        # the fake upstream response and lets the real endpoint do the work.
        # The production counting function remains in reporting.py.
        upstream_response = httpx.Response(
            200,
            json=self.records,
            request=httpx.Request("GET", "https://example.test/sightings"),
        )

        with patch("main.httpx.get", return_value=upstream_response):
            return self.client.get("/reports/trends", params=params)

    def test_weekly_and_monthly_boundaries(self):
        """Group dates across New Year and return the groups in date order."""
        # Weekly expectations:
        # - week starting 23 December: 29 December only -> 1
        # - week starting 30 December: 30 December, 4 and 5 January -> 3
        # - week starting 6 January: 6 January only -> 1
        # The week spanning New Year must stay together under its Monday label.
        #
        # Monthly expectations:
        # - December 2024: the two December sightings -> 2
        # - January 2025: the three January sightings, including Manchester -> 3
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
            # Label the weekly and monthly scenarios separately in test output.
            with self.subTest(period=period):
                response = self.get_report({"period": period})

                self.assertEqual(response.status_code, 200)
                result = response.json()

                # Check that cleaning happened before aggregation, then check
                # the exact group labels, totals and chronological list order.
                self.assertEqual(result["received"], 7)
                self.assertEqual(result["count"], 5)
                self.assertEqual(result["invalid_removed"], 1)
                self.assertEqual(result["duplicates_removed"], 1)
                self.assertEqual(result["trends"], expected)

    def test_location_and_date_filters(self):
        """Apply location and inclusive date limits before calculating trends."""
        # Request London from 30 December through 5 January, using mixed case
        # and surrounding whitespace to check location matching as well.
        # Keep the London sightings on 30 December and 5 January. Exclude the
        # other London dates and the Manchester sighting inside the date range.
        response = self.get_report({
            "period": "weekly",
            "location": "  lOnDoN  ",
            "start_date": "2024-12-30",
            "end_date": "2025-01-05",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

        # Both kept sightings belong to the week starting Monday 30 December,
        # even though one occurred in January. The last-day record at 23:59:59
        # must still count because the end date includes that whole calendar day.
        self.assertEqual(
            response.json()["trends"],
            [{"period_start": "2024-12-30", "count": 2}],
        )

    def test_no_matches_returns_empty_monthly_report(self):
        """Return an empty result and use monthly when no period is supplied."""
        # Every sample sighting predates 2026, so this valid query has no
        # matches. Omitting period also checks the endpoint's monthly default.
        response = self.get_report({"start_date": "2026-01-01"})

        # No matches is a successful search with an empty list, not an input
        # error. Check both the matching count and the returned report contents.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["period"], "monthly")
        self.assertEqual(response.json()["trends"], [])

    def test_invalid_inputs_return_422_without_fetching(self):
        """Reject unsupported periods and bad date inputs before fetching data."""
        # daily is outside the two allowed period values.
        # not-a-date fails FastAPI's date validation.
        # The reversed range has readable dates but is rejected by the shared
        # loading helper because its start date is later than its end date.
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
                # Unlike get_report(), this block does not supply sample data.
                # It records any attempted upstream GET, which should never
                # happen when a request can be rejected from its inputs alone.
                with patch("main.httpx.get") as mocked_get:
                    response = self.client.get("/reports/trends", params=params)

                self.assertEqual(response.status_code, 422)
                mocked_get.assert_not_called()
