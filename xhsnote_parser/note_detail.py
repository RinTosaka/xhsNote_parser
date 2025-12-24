import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

_INITIAL_STATE_PATTERN = re.compile(
    r"<script>window.__INITIAL_STATE__=(.*?)</script>", re.DOTALL
)


def extract_note_data(html: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Extract note section from the HTML script tag."""
    match = _INITIAL_STATE_PATTERN.search(html)
    if not match:
        logger.error("未在页面中找到 window.__INITIAL_STATE__ 脚本块")
        raise ValueError("页面结构不符合预期，无法解析 note 数据")
    raw_json = match.group(1).replace("undefined", "null")
    logger.debug("成功截取 __INITIAL_STATE__ JSON 字段，长度 %d", len(raw_json))
    full_state = json.loads(raw_json)
    note_section = full_state.get("note", {})
    return note_section, full_state


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
    path_prefix, trace_id = url_default.rsplit("/", 2)[1:]
    trace_id = trace_id.split("!")[0]
    if "_" not in path_prefix:
        extracted_path = f"{trace_id}"
    else:
        extracted_path = f"{path_prefix}/{trace_id}"
    return extracted_path or None


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
    originVideoKey = video_copy.get("consumer", "").get("originVideoKey", "")
    video_copy["urlNoWatermark"] = _build_nowatermark_video_default(originVideoKey)
    enriched.append(video_copy)
    logger.debug("处理 imageList 完成，共 %d 条", len(enriched))
    return enriched


def build_note_detail(note_data: Dict[str, Any], note_url: str) -> Dict[str, Any]:
    note_detail_map = note_data.get("noteDetailMap") or {}
    note_detail = _safe_first_note(note_detail_map)
    note_detail["imageList"] = _enrich_images(note_detail.get("imageList", []))
    if note_detail.get("video"):
        note_detail["video"] = _enrich_video(note_detail.get("video", []))
    note_detail["time"] = _format_timestamp(note_detail.get("time"))
    note_detail["lastUpdateTime"] = _format_timestamp(note_detail.get("lastUpdateTime"))
    note_detail["noteUrl"] = note_url
    return note_detail
