from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ParseOptions(BaseModel):
    timeout: Optional[int] = Field(
        default=None,
        ge=1,
        le=120,
        description="Request timeout in seconds. Uses server default if omitted.",
    )
    user_agent: Optional[str] = Field(default=None, description="Custom User-Agent.")
    cookie: Optional[str] = Field(default=None, description="Cookie header value.")
    save: bool = Field(default=True, description="Persist noteDetail JSON on disk.")
    save_initial_state: bool = Field(
        default=False, description="Persist window.__INITIAL_STATE__ JSON on disk."
    )

class ParseRequest(BaseModel):
    url: str = Field(..., description="Xiaohongshu note URL.")
    options: ParseOptions = Field(default_factory=ParseOptions)


class SavedPaths(BaseModel):
    note_detail: Optional[str] = Field(default=None, description="Saved noteDetail path.")
    initial_state: Optional[str] = Field(
        default=None, description="Saved initial_state path."
    )


class ParseResponse(BaseModel):
    url: str
    note: Dict[str, Any]
    saved: Optional[SavedPaths] = None
    initial_state: Optional[Dict[str, Any]] = None
    elapsed_ms: int


class BatchParseRequest(BaseModel):
    urls: List[str] = Field(..., description="List of note URLs.")
    options: ParseOptions = Field(default_factory=ParseOptions)
    concurrency: int = Field(default=3, ge=1, le=10)
    dedupe: bool = Field(default=True)


class BatchItem(BaseModel):
    url: str
    ok: bool
    result: Optional[ParseResponse] = None
    error: Optional[str] = None


class BatchResponse(BaseModel):
    items: List[BatchItem]
    total: int
    ok: int
    failed: int
    elapsed_ms: int


class OutputItemResponse(BaseModel):
    relative_path: str
    absolute_path: str
    size: int
    modified_time: str
    kind: str


class OutputListResponse(BaseModel):
    items: List[OutputItemResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    version: str
    time: str


class ConfigResponse(BaseModel):
    default_timeout: int
    output_dir: str
    cors_origins: List[str]
    save_log: bool
    log_dir: Optional[str]
