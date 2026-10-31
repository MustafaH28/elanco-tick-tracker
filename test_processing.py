"""Check that batch cleaning handles invalid and duplicate sightings correctly.

This uses a small set of pretend records so the expected result is easy to
understand and repeat. It tests data_processing directly, without downloading
Elanco's data or starting the web server.

Correct cleaning matters to the task because invalid or repeated reports
should not inflate the sighting list, regional totals or weekly/monthly totals.
"""

# unittest is Python's built-in testing framework. TestCase supplies methods
# such as assertEqual(), which fail a test when actual and expected values differ.
import unittest

# Import the same cleaning function that main.py uses for real API requests.
# This checks the project's implementation rather than recreating it in the test.
from data_processing import process_sightings


class TestProcessing(unittest.TestCase):
    """Group checks for cleaning a batch of raw sighting records."""

    def test_removes_invalid_and_duplicate_records(self):
        """Check the kept records and both removal counters in one example."""
        # Prepare a usable sighting containing the three required fields.
        # The date can be parsed, and the ID and location are non-empty text.
        # Optional species fields are unnecessary for this cleaning example.
        valid_record = {
            "id": "test-1",
            "date": "2024-06-15T12:00:00",
            "location": "London",
        }

        # Prepare a separate record with an unusable date. Its ID and location
        # are present, so the deliberately bad date should cause its rejection.
        invalid_record = {
            "id": "test-2",
            "date": "not-a-date",
            "location": "London",
        }

        # Build a batch of three records: one valid, one duplicate and one
        # invalid. copy() creates another dictionary with the same values,
        # including the same ID, to represent a repeated sighting report.
        records = [
            valid_record,
            valid_record.copy(),
            invalid_record,
        ]

        # Run the real cleaning function on this controlled input.
        # Its returned dictionary contains the kept records and cleanup counts.
        result = process_sightings(records)

        # assertEqual(actual, expected) checks each part of the result.
        # All three records were received, even though only one is retained.
        self.assertEqual(result["received"], 3)

        # Only one valid, unique sighting should remain after cleaning.
        self.assertEqual(result["count"], 1)

        # The record with "not-a-date" should be counted as invalid.
        self.assertEqual(result["invalid_removed"], 1)

        # The second copy of the valid record should be counted as a duplicate.
        self.assertEqual(result["duplicates_removed"], 1)

        # Check the actual contents as well as the counters: the remaining
        # list must contain the expected valid record and no extra records.
        self.assertEqual(result["sightings"], [valid_record])
