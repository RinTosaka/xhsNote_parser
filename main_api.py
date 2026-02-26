import os

import uvicorn


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


def main() -> None:
    host = _env_str("XHSNOTE_API_HOST", "127.0.0.1")
    port = _env_int("XHSNOTE_API_PORT", 8000)
    reload = _env_bool("XHSNOTE_API_RELOAD", True)
    uvicorn.run(
        "xhsnote_parser.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
