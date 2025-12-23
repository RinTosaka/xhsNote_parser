import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .http_client import DEFAULT_TIMEOUT
from .logging_utils import configure_logging, resolve_log_level
from .service import parse_note
from .storage import save_note_detail

logger = logging.getLogger(__name__)
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
_DEFAULT_OUTPUT_DIR = Path("output")
_DEFAULT_LOG_DIR = Path("logs")
_DEFAULT_ENV_PATH = Path(".env")


def _sanitize_segment(value: Optional[Any], fallback: str) -> str:
    if value in (None, ""):
        text = ""
    else:
        text = str(value)
    sanitized = []
    for char in text:
        if char in _INVALID_FILENAME_CHARS or ord(char) < 32:
            sanitized.append("_")
        else:
            sanitized.append(char)
    cleaned = "".join(sanitized).strip().rstrip(". ")
    return cleaned or fallback


def _build_output_path(note_detail: Dict[str, Any], base_dir: Path) -> Path:
    user = note_detail.get("user") or {}
    author = _sanitize_segment(user.get("nickname"), "unknown_author")
    title = _sanitize_segment(note_detail.get("title"), "untitled")
    note_id = _sanitize_segment(note_detail.get("noteId"), "note")
    filename = f"{title}_{note_id}_noteDetail.json"
    return base_dir / f"{author}_notes" / filename


def _load_urls_from_file(path: Path) -> List[str]:
    if not path.exists():
        raise ValueError(f"输入文件不存在: {path}")
    if not path.is_file():
        raise ValueError(f"输入路径不是文件: {path}")

    urls: List[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                text = raw_line.strip()
                if not text or text.startswith("#"):
                    continue
                urls.append(text)
    except OSError as exc:
        raise ValueError(f"读取输入文件失败: {path}: {exc}") from exc
    return urls


def _collect_input_urls(urls: Iterable[str], input_file: Optional[Path]) -> List[str]:
    collected: List[str] = []
    for url in urls:
        normalized = url.strip()
        if normalized:
            collected.append(normalized)

    if input_file:
        collected.extend(_load_urls_from_file(input_file))

    unique_urls: List[str] = []
    seen: set[str] = set()
    for url in collected:
        if url not in seen:
            unique_urls.append(url)
            seen.add(url)
    return unique_urls


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    if not path.is_file():
        raise ValueError(f".env 文件路径不是有效的文件: {path}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = _strip_quotes(value.strip())
    except OSError as exc:
        raise ValueError(f"读取 .env 文件失败: {path}: {exc}") from exc
    return env


def _resolve_int_option(
    cli_value: Optional[int],
    env_values: Dict[str, str],
    env_key: str,
    default: int,
    parser: argparse.ArgumentParser,
) -> int:
    if cli_value is not None:
        return cli_value
    raw_value = env_values.get(env_key)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        parser.error(f"{env_key} 必须是整数（.env 配置无效）: {exc}")


def _resolve_bool_option(
    cli_value: Optional[bool],
    env_values: Dict[str, str],
    env_key: str,
    default: bool,
    parser: argparse.ArgumentParser,
) -> bool:
    if cli_value is not None:
        return cli_value
    raw_value = env_values.get(env_key)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    parser.error(f"{env_key} 只能设置为 true/false")


def _resolve_log_level_option(
    cli_value: Optional[int],
    env_values: Dict[str, str],
    default: int,
    parser: argparse.ArgumentParser,
) -> int:
    if cli_value is not None:
        return cli_value
    raw_value = env_values.get("XHSNOTE_LOG_LEVEL")
    if raw_value is None:
        return default
    try:
        return resolve_log_level(raw_value)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    return default


def _resolve_path_option(
    cli_value: Optional[Path],
    env_values: Dict[str, str],
    env_key: str,
    default: Path,
) -> Path:
    if cli_value is not None:
        return cli_value
    raw_value = env_values.get(env_key)
    if not raw_value:
        return default
    return Path(raw_value).expanduser()


def _resolve_optional_path(
    cli_value: Optional[Path],
    env_values: Dict[str, str],
    env_key: str,
) -> Optional[Path]:
    if cli_value is not None:
        return cli_value
    raw_value = env_values.get(env_key)
    if not raw_value:
        return None
    return Path(raw_value).expanduser()


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="解析小红书笔记并输出 noteDetail.json"
    )
    parser.add_argument(
        "urls",
        nargs="*",
        help="需要解析的小红书 URL，可一次提供多个",
    )
    parser.add_argument(
        "-f",
        "--input-file",
        type=Path,
        help="包含 URL 的文本文件，每行一个，支持以 # 开头的注释",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="指定 .env 文件路径，默认会在当前目录查找同名文件",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="输出 JSON 所在目录，可通过 .env 设置，默认 output",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="请求超时时间（秒），默认 15，可在 .env 中覆盖",
    )
    parser.add_argument(
        "--user-agent",
        help="自定义 User-Agent 覆盖默认值",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        type=resolve_log_level,
        help="日志等级 (DEBUG/INFO/WARNING/ERROR)，默认 INFO",
    )
    parser.add_argument(
        "--save-log",
        dest="save_log",
        action="store_true",
        help="开启后将日志写入本地文件，可由 .env 预设默认值",
    )
    parser.add_argument(
        "--no-save-log",
        dest="save_log",
        action="store_false",
        help="显式关闭文件日志输出，优先级高于 .env",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="日志目录，默认 logs 或 .env 中的配置，仅当写文件日志时生效",
    )
    parser.set_defaults(save_log=None)
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    env_path = args.env_file if args.env_file is not None else _DEFAULT_ENV_PATH
    env_values: Dict[str, str] = {}
    if env_path.exists():
        try:
            env_values = _load_env_file(env_path)
            logger.debug("已加载 .env: %s", env_path)
        except ValueError as exc:
            parser.error(str(exc))
    elif args.env_file is not None:
        parser.error(f".env 文件不存在: {env_path}")

    timeout = _resolve_int_option(
        args.timeout,
        env_values,
        "XHSNOTE_TIMEOUT",
        DEFAULT_TIMEOUT,
        parser,
    )
    log_level = _resolve_log_level_option(
        args.log_level,
        env_values,
        logging.INFO,
        parser,
    )
    save_log = _resolve_bool_option(
        args.save_log,
        env_values,
        "XHSNOTE_SAVE_LOG",
        False,
        parser,
    )
    user_agent = args.user_agent or env_values.get("XHSNOTE_USER_AGENT")
    log_dir = _resolve_path_option(
        args.log_dir,
        env_values,
        "XHSNOTE_LOG_DIR",
        _DEFAULT_LOG_DIR,
    )
    output_dir = _resolve_path_option(
        args.output,
        env_values,
        "XHSNOTE_OUTPUT_DIR",
        _DEFAULT_OUTPUT_DIR,
    )
    input_file = _resolve_optional_path(
        args.input_file,
        env_values,
        "XHSNOTE_INPUT_FILE",
    )

    configure_logging(
        log_level,
        log_dir=log_dir,
        enable_file=save_log,
    )

    try:
        urls = _collect_input_urls(args.urls, input_file)
    except ValueError as exc:
        parser.error(str(exc))

    if not urls:
        parser.error("请通过 URL 参数或 --input-file 提供至少一个链接")

    headers: Dict[str, str] = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    total = len(urls)
    failures: List[str] = []

    for index, url in enumerate(urls, start=1):
        logger.info("解析进度 [%d/%d]: %s", index, total, url)
        try:
            note_detail = parse_note(
                url,
                headers=headers or None,
                timeout=timeout,
                output_path=None,
            )
            output_path = _build_output_path(note_detail, output_dir)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            save_note_detail(note_detail, output_path)
            logger.info("已保存到: %s", output_path)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("解析失败 [%s]: %s", url, exc)
            failures.append(url)

    if failures:
        logger.error("共有 %d 个 URL 解析失败", len(failures))
        raise SystemExit(1)

    logger.info("全部解析完成，共成功 %d 条", total)
