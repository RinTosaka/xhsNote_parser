from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .api_models import (
    BatchItem,
    BatchParseRequest,
    BatchResponse,
    ConfigResponse,
    HealthResponse,
    OutputItemResponse,
    OutputListResponse,
    ParseOptions,
    ParseRequest,
    ParseResponse,
    SavedPaths,
)
from .api_utils import build_output_path, delete_output_file, list_outputs, safe_resolve
from .logging_utils import configure_logging, resolve_log_level
from .note_detail import build_note_stub_from_initial_state
from .service import parse_note
from .storage import save_note_detail

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiSettings:
    default_timeout: int
    output_dir: Path
    cors_origins: List[str]
    allow_all_origins: bool
    save_log: bool
    log_dir: Optional[Path]
    static_dir: Optional[Path]
    version: str


class ParseFailure(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_note_id_from_url(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    path = (parsed.path or "").rstrip("/")
    if not path:
        return None
    candidate = path.split("/")[-1].strip()
    return candidate or None


_ALLOWED_MEDIA_SUFFIXES = (".xhscdn.com", ".xhscdn.net")


def _normalize_media_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("//"):
        return f"https:{cleaned}"
    return cleaned


def _is_allowed_media_host(host: Optional[str]) -> bool:
    if not host:
        return False
    lowered = host.lower()
    return any(
        lowered == suffix[1:] or lowered.endswith(suffix) for suffix in _ALLOWED_MEDIA_SUFFIXES
    )


def _env_str(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key)
    if raw is None:
        return default
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _resolve_log_level(default: int = logging.INFO) -> int:
    raw = os.getenv("XHSNOTE_LOG_LEVEL")
    if not raw:
        return default
    try:
        return resolve_log_level(raw)
    except Exception:
        return default


def load_settings() -> ApiSettings:
    default_timeout = _env_int("XHSNOTE_TIMEOUT", 15)
    output_dir = Path(_env_str("XHSNOTE_OUTPUT_DIR", "output")).expanduser()
    cors_origins = _env_list("XHSNOTE_API_CORS_ORIGINS", ["http://localhost:5173"])
    allow_all_origins = cors_origins == ["*"]
    save_log = _env_bool("XHSNOTE_SAVE_LOG", False)
    log_dir_raw = os.getenv("XHSNOTE_LOG_DIR")
    log_dir = Path(log_dir_raw).expanduser() if log_dir_raw else None
    static_enabled = _env_bool("XHSNOTE_API_ENABLE_STATIC", True)
    static_dir_raw = os.getenv("XHSNOTE_API_STATIC_DIR")
    if static_dir_raw:
        static_dir = Path(static_dir_raw).expanduser()
    else:
        static_dir = Path(__file__).resolve().parents[1] / "web" / "dist"
    if not static_enabled or not static_dir.exists():
        static_dir = None
    return ApiSettings(
        default_timeout=default_timeout,
        output_dir=output_dir,
        cors_origins=cors_origins,
        allow_all_origins=allow_all_origins,
        save_log=save_log,
        log_dir=log_dir,
        static_dir=static_dir,
        version="0.1.0",
    )


def _build_headers(options: ParseOptions) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if options.user_agent:
        headers["User-Agent"] = options.user_agent
    if options.cookie:
        headers["Cookie"] = options.cookie
    return headers


def _parse_note_sync(
    url: str, *, options: ParseOptions, settings: ApiSettings
) -> ParseResponse:
    start = time.perf_counter()
    initial_state_holder: Dict[str, Any] = {}

    def _capture(state: Dict[str, Any]) -> None:
        initial_state_holder["value"] = state
        if "saved_path" in initial_state_holder:
            return
        note_stub = build_note_stub_from_initial_state(state)
        if not note_stub.get("noteId"):
            fallback = _extract_note_id_from_url(url) or f"ts_{int(time.time() * 1000)}"
            note_stub["noteId"] = fallback
        initial_state_path = build_output_path(
            note_stub, settings.output_dir, suffix="initial_state"
        )
        initial_state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            save_note_detail(state, initial_state_path)
        except OSError as exc:
            logger.warning("保存 __INITIAL_STATE__ 失败: %s", exc)
            return
        initial_state_holder["saved_path"] = initial_state_path

    capture_state = options.save_initial_state
    timeout = options.timeout or settings.default_timeout
    headers = _build_headers(options)
    try:
        note_detail = parse_note(
            url,
            headers=headers or None,
            timeout=timeout,
            output_path=None,
            on_initial_state=_capture if capture_state else None,
        )
    except RuntimeError as exc:
        raise ParseFailure(str(exc), status_code=502) from exc
    except ValueError as exc:
        raise ParseFailure(str(exc), status_code=400) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise ParseFailure(f"Unexpected error: {exc}", status_code=500) from exc

    saved_paths: Optional[SavedPaths] = None
    if options.save:
        output_path = build_output_path(note_detail, settings.output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_note_detail(note_detail, output_path)
        saved_paths = SavedPaths(note_detail=str(output_path))

    if options.save_initial_state and "value" in initial_state_holder:
        desired_path = build_output_path(
            note_detail, settings.output_dir, suffix="initial_state"
        )
        saved_path = initial_state_holder.get("saved_path")
        if not (isinstance(saved_path, Path) and saved_path == desired_path):
            desired_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                if isinstance(saved_path, Path) and saved_path.exists():
                    if not desired_path.exists():
                        saved_path.replace(desired_path)
                    else:
                        save_note_detail(initial_state_holder["value"], desired_path)
                        saved_path.unlink(missing_ok=True)
                else:
                    save_note_detail(initial_state_holder["value"], desired_path)
            except OSError as exc:
                logger.warning("保存 __INITIAL_STATE__ 失败: %s", exc)
            else:
                initial_state_holder["saved_path"] = desired_path
        initial_state_path = initial_state_holder.get("saved_path")
        if isinstance(initial_state_path, Path):
            if saved_paths is None:
                saved_paths = SavedPaths(initial_state=str(initial_state_path))
            else:
                saved_paths.initial_state = str(initial_state_path)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    return ParseResponse(
        url=url,
        note=note_detail,
        saved=saved_paths,
        initial_state=initial_state_holder.get("value"),
        elapsed_ms=elapsed_ms,
    )


def create_app() -> FastAPI:
    settings = load_settings()
    configure_logging(
        _resolve_log_level(),
        log_dir=settings.log_dir,
        enable_file=settings.save_log,
    )

    app = FastAPI(title="xhsnote parser api", version=settings.version)
    app.state.settings = settings

    if settings.allow_all_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=settings.version,
            time=datetime.now(tz=timezone.utc).isoformat(),
        )

    @app.get("/api/config", response_model=ConfigResponse)
    async def config() -> ConfigResponse:
        return ConfigResponse(
            default_timeout=settings.default_timeout,
            output_dir=str(settings.output_dir),
            cors_origins=settings.cors_origins,
            save_log=settings.save_log,
            log_dir=str(settings.log_dir) if settings.log_dir else None,
        )

    @app.get("/api/media")
    async def media_proxy(request: Request, url: str) -> StreamingResponse:
        """代理 xhscdn 媒体资源，避免前端直连遇到混合内容/防盗链限制。"""

        if not url or len(url) > 4096:
            raise HTTPException(status_code=400, detail="Invalid url.")

        normalized = _normalize_media_url(url)
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"}:
            raise HTTPException(
                status_code=400, detail="Only http(s) URLs are allowed."
            )
        if not _is_allowed_media_host(parsed.hostname):
            raise HTTPException(status_code=400, detail="Media host is not allowed.")

        upstream_headers: Dict[str, str] = {
            "User-Agent": request.headers.get("user-agent", "Mozilla/5.0"),
            "Referer": "https://www.xiaohongshu.com/",
        }
        range_header = request.headers.get("range")
        if range_header:
            upstream_headers["Range"] = range_header

        try:
            upstream = requests.get(
                normalized,
                headers=upstream_headers,
                stream=True,
                timeout=settings.default_timeout,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502, detail=f"Upstream fetch failed: {exc}"
            ) from exc

        def iter_bytes():
            try:
                for chunk in upstream.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        passthrough_headers: Dict[str, str] = {}
        for key in [
            "content-type",
            "content-length",
            "content-range",
            "accept-ranges",
        ]:
            value = upstream.headers.get(key)
            if value:
                passthrough_headers[key] = value

        return StreamingResponse(
            iter_bytes(),
            status_code=upstream.status_code,
            headers=passthrough_headers,
            media_type=upstream.headers.get("content-type"),
        )

    @app.post("/api/parse", response_model=ParseResponse)
    async def parse_single(payload: ParseRequest) -> ParseResponse:
        url = payload.url.strip()
        if not url:
            raise HTTPException(status_code=400, detail="URL is required.")
        try:
            return await run_in_threadpool(
                _parse_note_sync,
                url,
                options=payload.options,
                settings=settings,
            )
        except ParseFailure as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.message
            ) from exc

    @app.post("/api/parse/batch", response_model=BatchResponse)
    async def parse_batch(payload: BatchParseRequest) -> BatchResponse:
        urls = [item.strip() for item in payload.urls if item.strip()]
        if payload.dedupe:
            urls = list(dict.fromkeys(urls))
        if not urls:
            raise HTTPException(status_code=400, detail="At least one URL is required.")

        semaphore = asyncio.Semaphore(payload.concurrency)
        results: List[Optional[BatchItem]] = [None] * len(urls)
        start = time.perf_counter()

        async def _run(index: int, url: str) -> None:
            async with semaphore:
                try:
                    result = await run_in_threadpool(
                        _parse_note_sync,
                        url,
                        options=payload.options,
                        settings=settings,
                    )
                    results[index] = BatchItem(url=url, ok=True, result=result)
                except ParseFailure as exc:
                    results[index] = BatchItem(url=url, ok=False, error=exc.message)
                except Exception as exc:  # pragma: no cover - defensive
                    results[index] = BatchItem(url=url, ok=False, error=str(exc))

        await asyncio.gather(*[_run(i, url) for i, url in enumerate(urls)])

        compact_results = [item for item in results if item is not None]
        ok_count = sum(1 for item in compact_results if item.ok)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return BatchResponse(
            items=compact_results,
            total=len(compact_results),
            ok=ok_count,
            failed=len(compact_results) - ok_count,
            elapsed_ms=elapsed_ms,
        )

    @app.get("/api/outputs", response_model=OutputListResponse)
    async def outputs(limit: int = 50) -> OutputListResponse:
        limit = max(1, min(limit, 200))
        items = list_outputs(settings.output_dir, limit=limit)
        return OutputListResponse(
            items=[OutputItemResponse(**item.__dict__) for item in items],
            total=len(items),
        )

    @app.get("/api/outputs/{relative_path:path}")
    async def output_file(relative_path: str) -> JSONResponse:
        try:
            target = safe_resolve(settings.output_dir, relative_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        try:
            content = target.read_text(encoding="utf-8")
            return JSONResponse(content=json.loads(content))
        except Exception as exc:
            logger.exception("Failed to read output file: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to read output file."
            ) from exc

    @app.delete("/api/outputs/{relative_path:path}")
    async def delete_output(relative_path: str) -> JSONResponse:
        try:
            deleted = delete_output_file(settings.output_dir, relative_path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        except IsADirectoryError as exc:
            raise HTTPException(status_code=400, detail="Target is not a file.") from exc
        except OSError as exc:
            logger.exception("Failed to delete output file: %s", exc)
            raise HTTPException(
                status_code=500, detail="Failed to delete output file."
            ) from exc
        deleted_relative = deleted.relative_to(settings.output_dir).as_posix()
        return JSONResponse(content={"ok": True, "deleted": deleted_relative})

    if settings.static_dir:
        app.mount(
            "/", StaticFiles(directory=settings.static_dir, html=True), name="static"
        )

    return app


app = create_app()
