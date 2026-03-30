"""High-level download orchestration for CLI and GUI clients."""

from pathlib import Path
from typing import Callable, Optional

from xjtlu_downloader.core.files import ensure_unique_filepath
from xjtlu_downloader.core.url_parser import parse_viewer_url, validate_url
from xjtlu_downloader.domain.models import DownloadResult, ETDAuthState, PreparedDownload, SessionResult
from xjtlu_downloader.infra.browser_downloader import BrowserPDFDownloader


class DownloadService:
    """Prepare and execute downloads through the browser-backed infrastructure."""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        user_data_dir: Optional[Path] = None,
    ):
        self.downloader = BrowserPDFDownloader(
            headless=headless,
            timeout=timeout,
            user_data_dir=user_data_dir,
        )

    def get_session_profile_dir(self) -> Path:
        """Return the app-managed browser profile directory."""
        return self.downloader.get_user_data_dir()

    def has_saved_session(self) -> bool:
        """Return whether an app-managed browser session already exists."""
        return self.downloader.has_session_profile()

    def clear_session(self) -> None:
        """Reset the app-managed browser session."""
        self.downloader.clear_session_profile()

    def get_site_auth_state(self) -> ETDAuthState:
        """Return the ETD website auth state stored in the app-managed profile."""
        return self.downloader.get_site_auth_state()

    def open_login_browser(
        self,
        start_url: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SessionResult:
        """Open the app-managed browser for interactive login."""
        return self.downloader.open_login_session(start_url=start_url, progress_callback=progress_callback)

    def prepare_download(self, viewer_url: str, output_dir: Path) -> PreparedDownload:
        """Validate a URL and prepare the target output path."""
        is_valid, error = validate_url(viewer_url)
        if not is_valid:
            raise ValueError(error)

        parsed = parse_viewer_url(viewer_url)
        if not parsed.success:
            raise ValueError(parsed.error or "URL 解析失败")

        record_id = parsed.record_id or "unknown"
        db_code = parsed.db_code or "EXAM"
        filename = f"{db_code}_{record_id}.pdf"

        output_dir.mkdir(parents=True, exist_ok=True)
        save_path = ensure_unique_filepath(output_dir / filename)

        return PreparedDownload(parsed_url=parsed, filename=filename, save_path=save_path)

    def download(
        self,
        viewer_url: str,
        output_dir: Path,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DownloadResult:
        """Validate the request, resolve the save path, and execute the download."""
        prepared = self.prepare_download(viewer_url, output_dir)
        return self.download_prepared(prepared, progress_callback)

    def download_prepared(
        self,
        prepared: PreparedDownload,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DownloadResult:
        """Execute a previously prepared download."""
        return self.downloader.download(
            viewer_url=prepared.parsed_url.viewer_url or "",
            save_path=str(prepared.save_path),
            progress_callback=progress_callback,
        )
