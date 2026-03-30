import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from xjtlu_downloader.domain.models import ETDAuthState
from xjtlu_downloader.infra.search_client import ETDAuthRequiredError, ETDSearchClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        if isinstance(self.payload, str):
            raise ValueError("not json")
        return self.payload

    @property
    def text(self):
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


class FakeSession:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.headers = {}
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.get_responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.post_responses.pop(0)


class SearchClientTests(unittest.TestCase):
    def test_build_search_payload_uses_contains_paper_code_and_fulltext(self):
        client = ETDSearchClient(ETDAuthState())
        config = {
            "dbId": 3,
            "sortField": [{"fieldName": "PaperTitle"}],
            "dbClass": [{"expression": "Year"}],
        }

        payload = client.build_search_payload("EEE205", config, page_index=2, page_size=50)

        self.assertEqual(payload["DbId"], 3)
        self.assertEqual(payload["PageIndex"], 2)
        self.assertEqual(payload["PageSize"], 50)
        self.assertEqual(payload["AdvancedSearchParams"][0]["SearchField"], "PaperCode")
        self.assertEqual(payload["AdvancedSearchParams"][0]["SearchType"], 2)
        self.assertEqual(payload["AdvancedSearchParams"][0]["SearchContent"], "EEE205")
        self.assertEqual(payload["AdvancedSearchParams"][1], {"SearchField": "FullText", "SearchContent": 1})
        self.assertEqual(payload["CategoryExpression"], "Year")

    def test_extract_record_id_accepts_sysid_case_variant(self):
        record_id = ETDSearchClient._extract_record_id({"syS_FLD_SYSID": 12621})
        self.assertEqual(record_id, "12621")

    def test_search_course_code_raises_auth_error_for_illegal_request(self):
        session = FakeSession(
            get_responses=[FakeResponse({"dbId": 3, "sortField": [], "dbClass": []})],
            post_responses=[FakeResponse('"非法请求"')],
        )
        client = ETDSearchClient(ETDAuthState(token="token", user_id="1"), session=session)

        with self.assertRaises(ETDAuthRequiredError):
            client.search_course_code("EEE205")

    def test_discover_course_viewer_urls_resolves_first_browser_url(self):
        session = FakeSession(
            get_responses=[
                FakeResponse(
                    {
                        "dbId": 3,
                        "sortField": [{"fieldName": "PaperTitle"}],
                        "dbClass": [{"expression": "Year"}],
                    }
                ),
                FakeResponse(
                    {
                        "detailResult": {
                            "isSuccess": True,
                            "hasBrowserRight": True,
                            "result": {"detailResult": [{"flag": 0}]},
                        }
                    }
                ),
                FakeResponse(
                    [
                        "/api/v1/File/BrowserFile?dbCode=EXAMXJTLU&recordId=12621;EXAMXJTLU_12621.pdf",
                    ]
                ),
            ],
            post_responses=[
                FakeResponse(
                    {
                        "isSuccess": True,
                        "recordCount": 1,
                        "result": {
                            "overviewResult": [
                                {
                                    "syS_FLD_SYSID": 12621,
                                    "PaperCode": "EEE205",
                                    "PaperTitle": "Digital Electronics II",
                                    "Year": "2024-2025",
                                }
                            ],
                            "columnInfo": [],
                        },
                    }
                )
            ],
        )
        client = ETDSearchClient(ETDAuthState(token="token", user_id="42"), session=session)

        discovered = client.discover_course_viewer_urls("EEE205")

        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].record_id, "12621")
        self.assertEqual(discovered[0].paper_code, "EEE205")
        self.assertIn("viewer.html?file=", discovered[0].viewer_url)
        self.assertIn("recordId%3D12621", discovered[0].viewer_url)


if __name__ == "__main__":
    unittest.main()
