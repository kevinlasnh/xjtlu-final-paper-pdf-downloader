"""Playwright-based downloader implementation."""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Callable, Optional

from playwright.async_api import TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from xjtlu_downloader.core.paths import get_browser_profile_dir
from xjtlu_downloader.domain.enums import DownloadErrorCode
from xjtlu_downloader.domain.models import (
    BrowserConfig,
    DownloadResult,
    DownloadTask,
    ETDAuthState,
    SessionResult,
)


class BrowserPDFDownloader:
    """Download PDFs by loading the viewer page in a real browser context."""

    ETD_HOME_URL = "https://etd.xjtlu.edu.cn/"
    ETD_INDEX_URL = "https://etd.xjtlu.edu.cn/index.html#/index"

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 60000,
        user_data_dir: Optional[Path] = None,
    ):
        self.config = BrowserConfig(
            headless=headless,
            timeout=timeout,
            user_data_dir=user_data_dir or get_browser_profile_dir(),
        )

    def get_user_data_dir(self) -> Path:
        """Return the persistent profile directory used by the downloader."""
        return Path(self.config.user_data_dir or get_browser_profile_dir())

    def has_session_profile(self) -> bool:
        """Check whether the persistent profile directory contains saved state."""
        profile_dir = self.get_user_data_dir()
        return profile_dir.exists() and any(profile_dir.iterdir())

    def clear_session_profile(self) -> None:
        """Delete the persistent profile directory and recreate it."""
        profile_dir = self.get_user_data_dir()
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)

    def get_site_auth_state(self) -> ETDAuthState:
        """Read the ETD website's login token and user id from the app profile."""
        loop = asyncio.new_event_loop()

        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._get_site_auth_state_async())
        except Exception as exc:
            return ETDAuthState(error=f"读取 ETD 登录状态失败：{exc}")
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    async def _launch_context(self, playwright, headless: bool):
        """Launch a persistent browser context backed by the app profile."""
        profile_dir = self.get_user_data_dir()
        profile_dir.mkdir(parents=True, exist_ok=True)

        return await playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            accept_downloads=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def _get_site_auth_state_async(self) -> ETDAuthState:
        """Async implementation used to inspect site auth state from local storage."""
        playwright = None
        context = None

        try:
            playwright = await async_playwright().start()
            context = await self._launch_context(playwright, headless=True)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(self.config.timeout)
            await page.goto(self.ETD_INDEX_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(500)

            storage = await page.evaluate(
                """() => ({
                    token: localStorage.getItem("token") || "",
                    userId: localStorage.getItem("uId") || "",
                    userName: localStorage.getItem("userName") || "",
                    role: localStorage.getItem("role") || "",
                    issuedTime: localStorage.getItem("issuedTime") || "",
                    expiresTime: localStorage.getItem("expriesTime") || ""
                })"""
            )

            return ETDAuthState(
                token=storage.get("token", ""),
                user_id=storage.get("userId", ""),
                user_name=storage.get("userName", ""),
                role=storage.get("role", ""),
                issued_time=storage.get("issuedTime", ""),
                expires_time=storage.get("expiresTime", ""),
            )
        except Exception as exc:
            return ETDAuthState(error=f"读取 ETD 登录状态失败：{exc}")
        finally:
            if context:
                await context.close()
            if playwright:
                await playwright.stop()

    def open_login_session(
        self,
        start_url: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SessionResult:
        """Open a persistent browser for interactive login and wait until closed."""
        loop = asyncio.new_event_loop()

        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._open_login_session_async(start_url, progress_callback))
        except Exception as exc:
            return SessionResult(success=False, message=f"登录浏览器启动失败：{exc}")
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    async def _open_login_session_async(
        self,
        start_url: Optional[str],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> SessionResult:
        """Async implementation of the interactive login flow."""
        playwright = None
        context = None

        def update_status(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        try:
            update_status("正在打开登录浏览器...")
            playwright = await async_playwright().start()
            context = await self._launch_context(playwright, headless=False)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(self.config.timeout)

            closed_future = asyncio.get_running_loop().create_future()

            def handle_close() -> None:
                if not closed_future.done():
                    closed_future.set_result(None)

            context.on("close", handle_close)

            await page.goto(start_url or self.ETD_HOME_URL, wait_until="domcontentloaded")
            await page.bring_to_front()
            update_status(
                "登录浏览器已打开。请在该窗口中完成 ETD 登录；登录完成后直接关闭整个浏览器窗口。"
            )

            await closed_future

            return SessionResult(
                success=self.has_session_profile(),
                message="登录浏览器已关闭，会话目录已更新。现在可以回到程序中重试下载。",
                profile_dir=self.get_user_data_dir(),
            )
        except Exception as exc:
            return SessionResult(
                success=False,
                message=f"登录浏览器流程失败：{exc}",
                profile_dir=self.get_user_data_dir(),
            )
        finally:
            if context:
                await context.close()
            if playwright:
                await playwright.stop()

    @staticmethod
    def _normalize_api_message(raw_text: str) -> str:
        """Normalize API error text into readable plain text."""
        text = raw_text.strip()
        if not text:
            return ""

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None

        if isinstance(parsed, str):
            return parsed

        if text.startswith('"') and text.endswith('"'):
            return text[1:-1]

        return text

    @classmethod
    def _build_api_error_message(cls, status: int, raw_text: str) -> str:
        """Build a user-facing message from a failed file API response."""
        message = cls._normalize_api_message(raw_text) or "未知错误"
        prefix = f"文件接口返回 {status}：{message}。"

        lowered = message.lower()
        if status in (401, 403) or "登录" in message or "非法请求" in message or "forbidden" in lowered:
            return (
                prefix
                + "该链接可能已过期，或当前浏览器/网络环境没有对应访问权限。"
                + "请回到 ETD 系统重新打开 PDF 并复制新链接。"
            )

        if status >= 500:
            return prefix + "服务端暂时不可用，请稍后重试。"

        return prefix + "请检查链接是否有效，并确认当前网络环境满足访问要求。"

    def download(
        self,
        viewer_url: str,
        save_path: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DownloadResult:
        """Run the async downloader in a dedicated event loop."""
        task = DownloadTask(viewer_url=viewer_url, save_path=Path(save_path))
        loop = asyncio.new_event_loop()

        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._download_async(task, progress_callback))
        except Exception as exc:
            return DownloadResult(
                success=False,
                error=f"程序内部错误：{exc}（请尝试重新运行程序）",
                error_code=DownloadErrorCode.INTERNAL_ERROR,
            )
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    async def _download_async(
        self,
        task: DownloadTask,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> DownloadResult:
        """Async implementation of the browser-backed download flow."""
        pdf_data = None
        api_error_message = None
        api_error_status = None
        playwright = None
        context = None

        def update_status(message: str) -> None:
            if progress_callback:
                progress_callback(message)

        try:
            update_status("正在启动浏览器...")
            playwright = await async_playwright().start()
            context = await self._launch_context(playwright, headless=self.config.headless)
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(self.config.timeout)

            async def handle_response(response) -> None:
                nonlocal api_error_message, api_error_status, pdf_data
                content_type = response.headers.get("content-type", "")
                url = response.url
                is_pdf = "pdf" in content_type.lower() or "octet-stream" in content_type.lower()
                is_api = "BrowserFile" in url or "api/v1/File" in url

                if not is_api:
                    return

                if is_pdf:
                    try:
                        pdf_data = await response.body()
                        update_status(f"已捕获PDF数据: {len(pdf_data)} 字节")
                    except Exception as exc:
                        update_status(f"捕获PDF失败: {exc}")
                    return

                if response.status >= 400:
                    try:
                        raw_text = await response.text()
                    except Exception:
                        raw_text = ""

                    api_error_status = response.status
                    api_error_message = self._build_api_error_message(response.status, raw_text)
                    update_status(f"文件接口返回错误: {response.status}")

            page.on("response", handle_response)

            update_status("正在打开PDF查看器页面...")
            response = await page.goto(task.viewer_url, wait_until="domcontentloaded")

            if response and response.status >= 400:
                return DownloadResult(
                    error=f"网络错误 {response.status}：无法访问页面（可能链接已过期或网络有问题）",
                    error_code=DownloadErrorCode.NETWORK_ERROR,
                )

            update_status("等待PDF加载中...请稍候")

            try:
                deadline = asyncio.get_running_loop().time() + 30
                while asyncio.get_running_loop().time() < deadline:
                    if pdf_data and len(pdf_data) > 1000:
                        break

                    if api_error_message:
                        return DownloadResult(
                            error=api_error_message,
                            error_code=DownloadErrorCode.ACCESS_DENIED,
                        )

                    error_wrapper = await page.query_selector(".errorWrapper")
                    if error_wrapper and await error_wrapper.is_visible():
                        error_msg = await page.query_selector("#errorMessage")
                        if error_msg:
                            message = f"PDF查看器报错: {await error_msg.inner_text()}（链接可能已过期）"
                        else:
                            message = "PDF查看器出错：链接可能已过期，请重新获取新链接"
                        return DownloadResult(error=message, error_code=DownloadErrorCode.VIEWER_ERROR)

                    await asyncio.sleep(0.25)

                if not pdf_data or len(pdf_data) < 1000:
                    page_content = await page.content()
                    if "errorMessage" in page_content and (
                        "expired" in page_content.lower() or "invalid" in page_content.lower()
                    ):
                        return DownloadResult(
                            error="链接已过期或无效：请回到ETD网站重新打开PDF并复制新链接",
                            error_code=DownloadErrorCode.VIEWER_ERROR,
                        )

            except PlaywrightTimeout:
                if api_error_message:
                    return DownloadResult(
                        error=api_error_message,
                        error_code=DownloadErrorCode.ACCESS_DENIED,
                    )

                error_wrapper = await page.query_selector(".errorWrapper")
                if error_wrapper:
                    error_msg = await page.query_selector("#errorMessage")
                    if error_msg:
                        message = f"PDF加载错误: {await error_msg.inner_text()}"
                    else:
                        message = "超时：PDF加载失败，链接可能已过期。\n如频繁超时，请尝试关闭VPN/代理后再试。"
                else:
                    message = "超时：等待PDF加载超时。\n如频繁超时，请关闭VPN/梯子/代理后重试。"
                return DownloadResult(error=message, error_code=DownloadErrorCode.TIMEOUT)

            if pdf_data and len(pdf_data) > 1000:
                update_status("正在保存PDF文件...")
                task.save_path.parent.mkdir(parents=True, exist_ok=True)

                with open(task.save_path, "wb") as output_file:
                    output_file.write(pdf_data)

                if task.save_path.exists() and task.save_path.stat().st_size > 0:
                    update_status("下载完成")
                    return DownloadResult(
                        success=True,
                        file_path=task.save_path,
                        file_size=task.save_path.stat().st_size,
                        error_code=DownloadErrorCode.NONE,
                    )

                return DownloadResult(
                    error="PDF文件保存失败：文件未正确写入磁盘（请检查磁盘空间和权限）",
                    error_code=DownloadErrorCode.SAVE_ERROR,
                )

            if pdf_data and len(pdf_data) <= 1000:
                return DownloadResult(
                    error=f"收到无效PDF数据（仅{len(pdf_data)}字节）：链接可能已过期，请重新获取",
                    error_code=DownloadErrorCode.INVALID_PDF,
                )

            if api_error_message:
                error_code = (
                    DownloadErrorCode.ACCESS_DENIED
                    if api_error_status in (401, 403)
                    else DownloadErrorCode.NETWORK_ERROR
                )
                return DownloadResult(error=api_error_message, error_code=error_code)

            return DownloadResult(
                error="无法获取PDF数据：链接很可能已过期，请回到浏览器重新打开PDF并复制新链接",
                error_code=DownloadErrorCode.NO_DATA,
            )
        except PlaywrightTimeout as exc:
            return DownloadResult(
                error=(
                    f"操作超时：{exc}\n\n"
                    "如频繁超时，请尝试：\n"
                    "1. 关闭电脑上的VPN/梯子/代理\n"
                    "2. 确保网络连接正常\n"
                    "3. 重新获取新的PDF链接"
                ),
                error_code=DownloadErrorCode.TIMEOUT,
            )
        except Exception as exc:
            error_message = str(exc)
            if "Executable doesn't exist" in error_message or "playwright install" in error_message:
                message = (
                    "未检测到可用的 Playwright Chromium 浏览器。\n\n"
                    "开发环境请先运行：python -m playwright install chromium\n"
                    "最终发布版需要把该浏览器一起打包，避免要求用户手动安装。"
                )
                code = DownloadErrorCode.BROWSER_MISSING
            elif "user data directory is already in use" in error_message.lower() or "singletonlock" in error_message.lower():
                message = "程序登录会话目录正被其他浏览器实例占用。请先关闭程序打开的登录浏览器窗口，再重试下载。"
                code = DownloadErrorCode.PROFILE_IN_USE
            elif "timeout" in error_message.lower() or "timed out" in error_message.lower():
                message = f"浏览器超时：{error_message}\n\n请关闭VPN/梯子/代理后重试。"
                code = DownloadErrorCode.TIMEOUT
            elif "network" in error_message.lower() or "connection" in error_message.lower():
                message = f"网络错误：{error_message}\n\n请检查网络连接是否正常"
                code = DownloadErrorCode.NETWORK_ERROR
            else:
                message = f"浏览器错误：{error_message}"
                code = DownloadErrorCode.INTERNAL_ERROR
            return DownloadResult(error=message, error_code=code)
        finally:
            if context:
                await context.close()
            if playwright:
                await playwright.stop()

    def get_suggested_filename(self, viewer_url: str, record_id: Optional[str] = None) -> str:
        """Generate a suggested filename from parsed metadata."""
        if record_id:
            return f"XJTLU_Document_{record_id}.pdf"
        return "XJTLU_Document.pdf"
