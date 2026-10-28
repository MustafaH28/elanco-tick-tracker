import unittest

from data_processing import process_sightings


class TestProcessing(unittest.TestCase):
    def test_removes_invalid_and_duplicate_records(self):
        valid_record = {
            "id": "test-1",
            "date": "2024-06-15T12:00:00",
            "location": "London",
        }

        invalid_record = {
            "id": "test-2",
            "date": "not-a-date",
            "location": "London",
        }

        records = [
            valid_record,
            valid_record.copy(),
            invalid_record,
        ]

        result = process_sightings(records)

        self.assertEqual(result["received"], 3)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["invalid_removed"], 1)
        self.assertEqual(result["duplicates_removed"], 1)
        self.assertEqual(result["sightings"], [valid_record])