import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_INITIAL_STATE_PATTERN = re.compile(
    r"window\.__INITIAL_STATE__\s*=", re.DOTALL
)


def _replace_undefined_outside_strings(raw_value: str) -> str:
    result: List[str] = []
    index = 0
    in_string: Optional[str] = None
    escaped = False

    while index < len(raw_value):
        char = raw_value[index]
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            index += 1
            continue

        if char in {'"', "'"}:
            in_string = char
            result.append(char)
            index += 1
            continue

        if raw_value.startswith("undefined", index):
            before = raw_value[index - 1] if index > 0 else ""
            after_index = index + len("undefined")
            after = raw_value[after_index] if after_index < len(raw_value) else ""
            if not (before.isalnum() or before == "_") and not (
                after.isalnum() or after == "_"
            ):
                result.append("null")
                index = after_index
                continue

        result.append(char)
        index += 1

    return "".join(result)


def _extract_balanced_js_value(source: str, start: int) -> str:
    while start < len(source) and source[start].isspace():
        start += 1
    if start >= len(source) or source[start] not in "{[":
        raise ValueError("window.__INITIAL_STATE__ 后未找到 JSON 对象")

    stack: List[str] = []
    in_string: Optional[str] = None
    escaped = False

    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue

        if char in {'"', "'"}:
            in_string = char
            continue

        if char in "{[":
            stack.append("}" if char == "{" else "]")
            continue

        if char in "}]":
            if not stack or char != stack[-1]:
                raise ValueError("window.__INITIAL_STATE__ JSON 括号不匹配")
            stack.pop()
            if not stack:
                return source[start : index + 1]

    raise ValueError("window.__INITIAL_STATE__ JSON 未闭合")


def extract_note_data(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract note section from the HTML script tag."""
    match = _INITIAL_STATE_PATTERN.search(html)
    if not match:
        logger.error("未在页面中找到 window.__INITIAL_STATE__ 脚本块")
        raise ValueError("页面结构不符合预期，无法解析 note 数据")
    try:
        raw_json = _extract_balanced_js_value(html, match.end())
    except ValueError as exc:
        logger.error("截取 window.__INITIAL_STATE__ 失败: %s", exc)
        raise ValueError("页面结构不符合预期，无法解析 note 数据") from exc
    raw_json = _replace_undefined_outside_strings(raw_json)
    logger.debug("成功截取 __INITIAL_STATE__ JSON 字段，长度 %d", len(raw_json))
    full_state = json.loads(raw_json)
    note_section = full_state.get("note", {})
    return note_section, full_state


def build_note_stub_from_initial_state(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort build a minimal note_detail-like dict from window.__INITIAL_STATE__.

    该返回值可用于命名输出文件（例如 initial_state 的落盘路径），即使后续解析失败，
    也尽量能生成稳定的文件名。
    """

    note_section = initial_state.get("note")
    if not isinstance(note_section, dict):
        return {}

    note_detail_map = note_section.get("noteDetailMap")
    if not isinstance(note_detail_map, dict):
        return {}

    for entry in note_detail_map.values():
        if not isinstance(entry, dict):
            continue
        note = entry.get("note")
        if not isinstance(note, dict) or not note:
            continue

        stub: Dict[str, Any] = {}
        if "title" in note:
            stub["title"] = note.get("title")
        note_id = note.get("noteId") or note.get("id")
        if note_id:
            stub["noteId"] = note_id
        user = note.get("user")
        if isinstance(user, dict) and user:
            stub["user"] = user
        return stub

    return {}


def _safe_first_note(note_detail_map: Dict[str, Any]) -> Dict[str, Any]:
    for entry in note_detail_map.values():
        note = entry.get("note")
        if note:
            logger.debug("命中 noteDetailMap 中的第一条笔记数据")
            return dict(note)
    logger.error("noteDetailMap 中未找到 note 字段")
    raise ValueError("noteDetailMap 不包含 note 信息")


def _format_timestamp(ms_value: Optional[int]) -> Optional[str]:
    if not ms_value:
        return None
    try:
        formatted = datetime.fromtimestamp(ms_value / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        logger.debug("时间戳 %s -> %s", ms_value, formatted)
        return formatted
    except (ValueError, TypeError) as exc:
        logger.warning("无法格式化时间戳 %s: %s", ms_value, exc)
        return None


def _extract_path(url_default: str) -> Optional[str]:
    if not url_default:
        return None
    parsed = urlparse(url_default)
    segments = [segment for segment in (parsed.path or "").split("/") if segment]
    if not segments:
        return None
    trace_id = segments[-1].split("!")[0]
    if len(segments) >= 2:
        path_prefix = segments[-2]
        if "_" in path_prefix or path_prefix == "spectrum":
            extracted_path = f"{path_prefix}/{trace_id}"
            return extracted_path or None
    return trace_id or None


def _build_nowatermark_imgUrl_default(extracted_path: str) -> str:
    return f"https://sns-img-hw.xhscdn.com/{extracted_path}?imageView2/2/w/0/format/jpg"


def _build_nowatermark_video_default(originVideoKey: str) -> str:
    return f"https://sns-video-hw.xhscdn.com/{originVideoKey}"


def _enrich_images(images: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for image in images:
        if not isinstance(image, dict):
            continue
        image_copy = dict(image)
        extracted_path = _extract_path(image_copy.get("urlDefault", ""))
        if extracted_path:
            image_copy["extracted_path"] = extracted_path
            trace_id = extracted_path.split("/")[-1]
            image_copy["traceId"] = trace_id
            image_copy["urlNoWatermark"] = _build_nowatermark_imgUrl_default(
                extracted_path
            )
        enriched.append(image_copy)
    logger.debug("处理 imageList 完成，共 %d 条", len(enriched))
    return enriched


def _enrich_video(video: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    video_copy = dict(video)
    originVideoKey = video_copy.get("media", "").get("videoId", "")
    video_copy["urlNoWatermark"] = _build_nowatermark_video_default(originVideoKey)
    enriched.append(video_copy)
    logger.debug("处理 imageList 完成，共 %d 条", len(enriched))
    return enriched


def build_note_detail(note_data: Dict[str, Any], note_url: str) -> Dict[str, Any]:
    note_detail_map = note_data.get("noteDetailMap") or {}
    note_detail = _safe_first_note(note_detail_map)
    note_detail["imageList"] = _enrich_images(note_detail.get("imageList", []))
    # if note_detail.get("video"):
    #     note_detail["video"] = _enrich_video(note_detail.get("video", []))
    create_time = _format_timestamp(note_detail.get("time"))
    note_detail["CreateTime"] = create_time
    note_detail.pop("time", None)
    note_detail["lastUpdateTime"] = _format_timestamp(note_detail.get("lastUpdateTime"))
    note_detail["noteUrl"] = note_url
    return note_detail
