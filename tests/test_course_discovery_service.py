import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from xjtlu_downloader.core.course_discovery_service import CourseDiscoveryService
from xjtlu_downloader.domain.models import DiscoveredViewerUrl, ETDAuthState
from xjtlu_downloader.infra.search_client import ETDAuthRequiredError


class FakeSearchClient:
    def __init__(self, auth_state: ETDAuthState):
        self.auth_state = auth_state

    def discover_course_viewer_urls(self, course_code: str) -> list[DiscoveredViewerUrl]:
        if course_code == "EEE205":
            return [
                DiscoveredViewerUrl(course_code="EEE205", record_id="1", viewer_url="https://example.com/1"),
                DiscoveredViewerUrl(course_code="EEE205", record_id="2", viewer_url="https://example.com/2"),
            ]

        if course_code == "CPT210":
            return [
                DiscoveredViewerUrl(course_code="CPT210", record_id="2", viewer_url="https://example.com/2"),
                DiscoveredViewerUrl(course_code="CPT210", record_id="3", viewer_url="https://example.com/3"),
            ]

        return []


class CourseDiscoveryServiceTests(unittest.TestCase):
    def test_normalize_course_codes_deduplicates(self):
        normalized = CourseDiscoveryService.normalize_course_codes(["eee205", " ", "CPT210", "EEE205"])
        self.assertEqual(normalized, ["EEE205", "CPT210"])

    def test_discover_viewer_urls_requires_site_auth(self):
        service = CourseDiscoveryService(search_client_factory=FakeSearchClient)
        service.get_site_auth_state = lambda: ETDAuthState()

        with self.assertRaises(ETDAuthRequiredError):
            service.discover_viewer_urls(["EEE205"])

    def test_discover_viewer_urls_deduplicates_record_ids_across_courses(self):
        service = CourseDiscoveryService(search_client_factory=FakeSearchClient)
        service.get_site_auth_state = lambda: ETDAuthState(token="token", user_id="42")

        items = service.discover_viewer_urls(["EEE205", "CPT210"])

        self.assertEqual([item.record_id for item in items], ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
