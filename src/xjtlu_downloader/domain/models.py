"""Domain models for parsing, search discovery, tasks, and download results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from .enums import DownloadErrorCode


@dataclass
class ParsedViewerUrl:
    """Parsed metadata extracted from an ETD viewer URL."""

    viewer_url: Optional[str] = None
    record_id: Optional[str] = None
    db_code: Optional[str] = None
    success: bool = False
    error: Optional[str] = None

    def to_legacy_dict(self) -> Dict[str, Optional[str]]:
        """Expose the original dict-shaped API during migration."""
        return {
            "viewer_url": self.viewer_url,
            "record_id": self.record_id,
            "db_code": self.db_code,
            "success": self.success,
            "error": self.error,
        }


@dataclass(frozen=True)
class BrowserConfig:
    """Browser launch options shared by the Playwright runtime."""

    headless: bool = True
    timeout: int = 60000
    user_data_dir: Optional[Path] = None


@dataclass(frozen=True)
class DownloadTask:
    """Single download request passed to the downloader core."""

    viewer_url: str
    save_path: Path
    record_id: Optional[str] = None
    db_code: Optional[str] = None


@dataclass(frozen=True)
class PreparedDownload:
    """Validated download prepared for execution."""

    parsed_url: ParsedViewerUrl
    filename: str
    save_path: Path


@dataclass
class DownloadResult:
    """Structured result returned by the downloader core."""

    success: bool = False
    file_path: Optional[Path] = None
    file_size: int = 0
    error: Optional[str] = None
    error_code: DownloadErrorCode = field(default=DownloadErrorCode.NONE)

    def to_legacy_dict(self) -> Dict[str, Optional[str]]:
        """Expose the original dict-shaped API during migration."""
        return {
            "success": self.success,
            "file_path": str(self.file_path) if self.file_path else None,
            "file_size": self.file_size,
            "error": self.error,
        }


@dataclass
class SessionResult:
    """Result returned by interactive session actions."""

    success: bool = False
    message: str = ""
    profile_dir: Optional[Path] = None

    def to_legacy_dict(self) -> Dict[str, Optional[str]]:
        """Expose a dict-shaped API for UI workers."""
        return {
            "success": self.success,
            "message": self.message,
            "profile_dir": str(self.profile_dir) if self.profile_dir else None,
        }


@dataclass(frozen=True)
class ETDAuthState:
    """Login state extracted from the ETD site's local storage."""

    token: str = ""
    user_id: str = ""
    user_name: str = ""
    role: str = ""
    issued_time: str = ""
    expires_time: str = ""
    error: Optional[str] = None

    @property
    def is_authenticated(self) -> bool:
        """Return whether the ETD site token and user id are present."""
        return bool(self.token and self.user_id)


@dataclass(frozen=True)
class CoursePaperHit:
    """Single search hit returned by course-code discovery."""

    course_code: str
    record_id: str
    paper_code: str = ""
    paper_title: str = ""
    year: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveredViewerUrl:
    """Resolved viewer URL plus metadata for a discovered paper."""

    course_code: str
    record_id: str
    viewer_url: str
    paper_code: str = ""
    paper_title: str = ""
    year: str = ""
