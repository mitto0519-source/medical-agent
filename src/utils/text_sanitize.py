"""Text sanitization — JSON/API 전송 안전 보장.

배경 (2026-05-30 incident):
    Claude API 호출이 `400 The request body is not valid JSON: no low surrogate
    in string: line 1 column 6607143` 으로 영구 차단됐다. 원인은 약 6.6MB의
    요청 본문 안에 **고립된 UTF-16 surrogate**(low surrogate 없는 high surrogate
    `\\uD800–\\uDBFF`, 또는 high surrogate 없는 low surrogate `\\uDC00–\\uDFFF`)
    가 들어가 JSON 직렬화가 실패한 것. 한 번 컨텍스트에 끼면 매 turn 같은 본문이
    재전송되어 세션 전체가 사망한다.

방어 원칙:
    1. **저장 직전 차단**: 외부에서 들어온 텍스트를 디스크/DB에 쓰기 전에 lone
       surrogate를 제거한다. 들어간 뒤 청소하는 것보다 들어가지 않게 막는다.
    2. **재귀 sanitize**: dict/list 안 임의 깊이의 str까지 훑는다.
    3. **graceful**: 실패해도 None 반환·예외 무시. 이 모듈 때문에 본 동작이
       멈추면 안 된다 (의료 도메인은 부분 결과라도 살아있어야 함).

사용:
    from src.utils.text_sanitize import strip_lone_surrogates, safe_json_dumps
    safe_text = strip_lone_surrogates(user_input)
    payload = safe_json_dumps(big_dict)
"""
from __future__ import annotations

import json
import re
from typing import Any

# High surrogate without following low | Low surrogate without preceding high
_LONE_SURROGATE = re.compile(
    r"[\ud800-\udbff](?![\udc00-\udfff])|(?<![\ud800-\udbff])[\udc00-\udfff]"
)

# JSON에 들어가면 안 되는 제어문자 (NUL 등). \n/\r/\t는 json.dumps가 \\n으로 처리하므로 OK.
_BAD_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

REPLACEMENT = "�"  # Unicode replacement character (U+FFFD)


def strip_lone_surrogates(text: Any, *, replacement: str = REPLACEMENT) -> str:
    """입력을 str로 변환한 뒤 lone surrogate와 nasty control char를 제거.

    - None/숫자/None 등 비문자열은 str()로 변환 후 처리.
    - 결과는 UTF-8로 안전하게 인코딩 가능함이 보장된다.
    - replacement="" 주면 통째로 삭제(길이 단축), 기본은 U+FFFD로 대체.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = str(text)
        except Exception:
            return ""
    cleaned = _LONE_SURROGATE.sub(replacement, text)
    cleaned = _BAD_CTRL.sub("", cleaned)
    # 최종 보증 — utf-8 인코딩이 진짜 되는지 확인. 안 되면 errors='replace'로 강제.
    try:
        cleaned.encode("utf-8")
    except UnicodeEncodeError:
        cleaned = cleaned.encode("utf-8", errors="replace").decode("utf-8")
    return cleaned


def sanitize_obj(obj: Any, *, max_str_len: int | None = None) -> Any:
    """dict/list/tuple 안 임의 깊이의 str을 재귀적으로 sanitize.

    - max_str_len 지정 시 각 str을 그 길이로 잘라낸다(거대 message가 컨텍스트
      폭주의 또 다른 축이라 같이 막아둠).
    - dict 키도 sanitize한다.
    - set은 list로 변환.
    """
    if isinstance(obj, str):
        s = strip_lone_surrogates(obj)
        if max_str_len is not None and len(s) > max_str_len:
            s = s[:max_str_len] + "…[truncated]"
        return s
    if isinstance(obj, dict):
        return {
            strip_lone_surrogates(k): sanitize_obj(v, max_str_len=max_str_len)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [sanitize_obj(x, max_str_len=max_str_len) for x in obj]
    if isinstance(obj, set):
        return [sanitize_obj(x, max_str_len=max_str_len) for x in obj]
    return obj


def safe_json_dumps(obj: Any, *, max_str_len: int | None = None, **kwargs: Any) -> str:
    """json.dumps에 sanitize를 한 번 거쳐서 직렬화.

    - default ensure_ascii=False (한글 그대로 유지)
    - default default=str (datetime 등 자동 처리)
    - max_str_len: 거대 문자열 자르기 한도 (필요 시)
    """
    kwargs.setdefault("ensure_ascii", False)
    kwargs.setdefault("default", str)
    safe = sanitize_obj(obj, max_str_len=max_str_len)
    return json.dumps(safe, **kwargs)


def scan_lone_surrogates(text: str) -> list[int]:
    """text 안 lone surrogate의 모든 시작 인덱스 반환 (audit 용)."""
    if not isinstance(text, str):
        return []
    return [m.start() for m in _LONE_SURROGATE.finditer(text)]


def is_safe(text: Any) -> bool:
    """text가 lone surrogate / nasty ctrl 모두 없으면 True."""
    if text is None:
        return True
    if not isinstance(text, str):
        return is_safe(str(text))
    if _LONE_SURROGATE.search(text):
        return False
    if _BAD_CTRL.search(text):
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


__all__ = [
    "strip_lone_surrogates",
    "sanitize_obj",
    "safe_json_dumps",
    "scan_lone_surrogates",
    "is_safe",
    "REPLACEMENT",
]
