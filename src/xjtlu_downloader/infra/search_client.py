"""HTTP client for course-code search and viewer URL discovery."""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote

import requests

from xjtlu_downloader.domain.models import CoursePaperHit, DiscoveredViewerUrl, ETDAuthState


class ETDSearchError(RuntimeError):
    """Raised when the ETD search API returns an unexpected failure."""


class ETDAuthRequiredError(ETDSearchError):
    """Raised when a search action needs a logged-in ETD site session."""


class ETDSearchClient:
    """Query ETD search endpoints and resolve search hits into viewer URLs."""

    BASE_URL = "https://etd.xjtlu.edu.cn"
    EXAM_DB_CODE = "EXAMXJTLU"
    DEFAULT_TIMEOUT = 30

    def __init__(self, auth_state: ETDAuthState, session: Optional[requests.Session] = None):
        self.auth_state = auth_state
        self.session = session or requests.Session()
        if auth_state.token:
            self.session.headers.setdefault("Authorization", f"bearer {auth_state.token}")

    @staticmethod
    def _normalize_scalar(value: Any) -> str:
        """Convert scalar response values into stripped strings."""
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_key(value: str) -> str:
        """Normalize a response key for case-insensitive matching."""
        return "".join(ch.lower() for ch in str(value) if ch.isalnum())

    @classmethod
    def _pick_value(cls, mapping: dict[str, Any], *names: str) -> str:
        """Return the first non-empty value matching any candidate key."""
        normalized = {cls._normalize_key(key): value for key, value in mapping.items()}

        for name in names:
            value = normalized.get(cls._normalize_key(name))
            if value not in (None, ""):
                return cls._normalize_scalar(value)

        return ""

    @classmethod
    def _extract_record_id(cls, row: dict[str, Any]) -> str:
        """Extract the ETD record id from a search row."""
        for name in ("syS_FLD_SYSID", "recordId", "record_id", "sysId"):
            value = cls._pick_value(row, name)
            if value:
                return value

        normalized = {cls._normalize_key(key): value for key, value in row.items()}
        for key, value in normalized.items():
            if key.endswith("sysid") and value not in (None, ""):
                return cls._normalize_scalar(value)

        raise ETDSearchError("检索结果中缺少 record id，无法继续解析 viewer URL。")

    @staticmethod
    def _parse_response(response: requests.Response) -> Any:
        """Parse a JSON API response, falling back to plain text."""
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return response.text.strip()

    @staticmethod
    def _error_message(payload: Any) -> str:
        """Extract a readable error message from a response payload."""
        if isinstance(payload, str):
            return payload.strip().strip('"')

        if isinstance(payload, dict):
            for key in ("errorInfo", "message", "messageDetail"):
                value = payload.get(key)
                if value:
                    return str(value)

        return ""

    @classmethod
    def _ensure_success(cls, payload: Any) -> Any:
        """Raise a typed error for auth failures or unexpected API failures."""
        message = cls._error_message(payload)
        if isinstance(payload, str) and message:
            if "非法请求" in message or "登录" in message:
                raise ETDAuthRequiredError(
                    "课程代码检索需要 ETD 网站登录态。请先在程序中点击“登录 ETD”，并在 ETD 首页完成登录。"
                )
            raise ETDSearchError(message)

        if isinstance(payload, dict) and payload.get("isSuccess") is False:
            if "非法请求" in message or "登录" in message:
                raise ETDAuthRequiredError(
                    "课程代码检索需要 ETD 网站登录态。请先在程序中点击“登录 ETD”，并在 ETD 首页完成登录。"
                )
            raise ETDSearchError(message or "ETD 搜索接口返回失败。")

        return payload

    def get_exam_search_config(self) -> dict[str, Any]:
        """Fetch search metadata for the exam-paper database."""
        response = self.session.get(
            f"{self.BASE_URL}/api/v1/Search/{self.EXAM_DB_CODE}",
            timeout=self.DEFAULT_TIMEOUT,
        )
        payload = self._ensure_success(self._parse_response(response))
        if not isinstance(payload, dict):
            raise ETDSearchError("试卷检索配置返回结构异常。")
        return payload

    def build_search_payload(
        self,
        course_code: str,
        config: dict[str, Any],
        *,
        page_index: int,
        page_size: int,
    ) -> dict[str, Any]:
        """Build the same search payload used by the official search page."""
        sort_fields = config.get("sortField") or []
        db_classes = config.get("dbClass") or []

        order_field = sort_fields[0].get("fieldName") if sort_fields else "PaperTitle"
        category_expression = db_classes[0].get("expression") if db_classes else ""

        return {
            "DbId": config.get("dbId"),
            "DbCode": self.EXAM_DB_CODE,
            "OrderField": order_field,
            "PageIndex": page_index,
            "PageSize": page_size,
            "AdvancedSearchParams": [
                {
                    "SearchType": 2,
                    "SearchField": "PaperCode",
                    "SearchContent": course_code,
                },
                {
                    "SearchField": "FullText",
                    "SearchContent": 1,
                },
            ],
            "CategoryExpression": category_expression,
            "CatalogCode": "",
        }

    def search_course_code(self, course_code: str, page_size: int = 50) -> list[CoursePaperHit]:
        """Return every search hit for a course code across all result pages."""
        normalized_code = course_code.strip().upper()
        if not normalized_code:
            return []

        config = self.get_exam_search_config()
        hits = []
        page_index = 1
        total_count = None

        while True:
            payload = self.build_search_payload(
                normalized_code,
                config,
                page_index=page_index,
                page_size=page_size,
            )
            response = self.session.post(
                f"{self.BASE_URL}/api/v1/Search/Search",
                json=payload,
                timeout=self.DEFAULT_TIMEOUT,
            )
            body = self._ensure_success(self._parse_response(response))
            if not isinstance(body, dict):
                raise ETDSearchError("试卷检索结果返回结构异常。")

            result = body.get("result") or {}
            rows = result.get("overviewResult") or []
            total_count = int(body.get("recordCount") or 0)

            for row in rows:
                if not isinstance(row, dict):
                    continue

                hits.append(
                    CoursePaperHit(
                        course_code=normalized_code,
                        record_id=self._extract_record_id(row),
                        paper_code=self._pick_value(row, "PaperCode"),
                        paper_title=self._pick_value(row, "PaperTitle"),
                        year=self._pick_value(row, "Year"),
                        raw=dict(row),
                    )
                )

            if not rows:
                break

            if total_count and page_index * page_size >= total_count:
                break

            page_index += 1

        return hits

    def resolve_viewer_url(
        self,
        record_id: str,
        *,
        db_id: int = 3,
        db_code: str = EXAM_DB_CODE,
    ) -> str:
        """Resolve a record id into the viewer URL used by the existing downloader."""
        if not self.auth_state.user_id:
            raise ETDAuthRequiredError("当前程序会话中没有可用的 ETD userId，请先重新登录。")

        params = {
            "dbId": db_id,
            "dbCode": db_code,
            "recordId": record_id,
            "userId": self.auth_state.user_id,
        }

        detail_response = self.session.get(
            f"{self.BASE_URL}/api/v1/Detail",
            params=params,
            timeout=self.DEFAULT_TIMEOUT,
        )
        detail_payload = self._ensure_success(self._parse_response(detail_response))
        if not isinstance(detail_payload, dict):
            raise ETDSearchError("详情接口返回结构异常。")

        detail_result = detail_payload.get("detailResult") or {}
        if not detail_result.get("isSuccess"):
            raise ETDSearchError(self._error_message(detail_result) or "读取试卷详情失败。")
        if not detail_result.get("hasBrowserRight"):
            raise ETDSearchError(f"当前账号对记录 {record_id} 没有在线浏览权限。")

        detail_rows = (detail_result.get("result") or {}).get("detailResult") or []
        detail_row = detail_rows[0] if detail_rows else {}
        flag = detail_row.get("flag", 0)

        browser_response = self.session.get(
            f"{self.BASE_URL}/api/v1/file/BrowserUrl/{flag}",
            params=params,
            timeout=self.DEFAULT_TIMEOUT,
        )
        browser_payload = self._ensure_success(self._parse_response(browser_response))
        browser_urls = self._extract_browser_urls(browser_payload)
        if not browser_urls:
            raise ETDSearchError(f"记录 {record_id} 没有可用的在线浏览地址。")

        browser_file_url = browser_urls[0]
        return (
            f"{self.BASE_URL}/static/readonline/web/viewer.html?"
            f"file={quote(browser_file_url, safe='')}"
        )

    @classmethod
    def _extract_browser_urls(cls, payload: Any) -> list[str]:
        """Normalize BrowserUrl API responses into plain file URLs."""
        if isinstance(payload, list):
            raw_items = payload
        elif isinstance(payload, str):
            raw_items = [payload]
        else:
            raise ETDSearchError("在线浏览地址返回结构异常。")

        urls = []
        for item in raw_items:
            text = cls._normalize_scalar(item)
            if not text:
                continue
            urls.append(text.split(";")[0].strip())

        return urls

    def discover_course_viewer_urls(self, course_code: str) -> list[DiscoveredViewerUrl]:
        """Search a course code and resolve every unique hit into a viewer URL."""
        discovered = []
        seen_record_ids = set()

        for hit in self.search_course_code(course_code):
            if hit.record_id in seen_record_ids:
                continue

            viewer_url = self.resolve_viewer_url(hit.record_id)
            discovered.append(
                DiscoveredViewerUrl(
                    course_code=hit.course_code,
                    record_id=hit.record_id,
                    viewer_url=viewer_url,
                    paper_code=hit.paper_code,
                    paper_title=hit.paper_title,
                    year=hit.year,
                )
            )
            seen_record_ids.add(hit.record_id)

        return discovered
