import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_INITIAL_STATE_PATTERN = re.compile(
    r"<script>window.__INITIAL_STATE__=(.*?)</script>", re.DOTALL
)


def extract_note_data(html: str) -> Dict[str, Any]:
    """Extract note section from the HTML script tag."""
    match = _INITIAL_STATE_PATTERN.search(html)
    if not match:
        logger.error("未在页面中找到 window.__INITIAL_STATE__ 脚本块")
        raise ValueError("页面结构不符合预期，无法解析 note 数据")
    raw_json = match.group(1).replace("undefined", "null")
    logger.debug("成功截取 __INITIAL_STATE__ JSON 字段，长度 %d", len(raw_json))
    full_state = json.loads(raw_json)
    return full_state.get("note", {})


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


def _extract_trace_id(url_default: str) -> Optional[str]:
    if not url_default:
        return None
    trace_id = url_default.rsplit("/", 1)[-1].split("!")[0]
    return trace_id or None


def _build_nowatermark_url(trace_id: str) -> str:
    return (
        f"https://sns-img-hw.xhscdn.com/notes_pre_post/{trace_id}"
        "?imageView2/2/w/0/format/jpg"
    )


def _enrich_images(images: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = []
    for image in images:
        if not isinstance(image, dict):
            continue
        image_copy = dict(image)
        trace_id = _extract_trace_id(image_copy.get("urlDefault", ""))
        if trace_id:
            image_copy["traceId"] = trace_id
            image_copy["urlNoWatermark"] = _build_nowatermark_url(trace_id)
        enriched.append(image_copy)
    logger.debug("处理 imageList 完成，共 %d 条", len(enriched))
    return enriched


def build_note_detail(note_data: Dict[str, Any], note_url: str) -> Dict[str, Any]:
    note_detail_map = note_data.get("noteDetailMap") or {}
    note_detail = _safe_first_note(note_detail_map)
    note_detail["imageList"] = _enrich_images(note_detail.get("imageList", []))
    note_detail["time"] = _format_timestamp(note_detail.get("time"))
    note_detail["lastUpdateTime"] = _format_timestamp(
        note_detail.get("lastUpdateTime")
    )
    note_detail["noteUrl"] = note_url
    return note_detail
