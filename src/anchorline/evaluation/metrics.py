# -*- coding: utf-8 -*-
"""V2 官方判分函数的移植（确定性部分）。

来源：LongMemEval-V2 `evaluation/qa_eval_metrics.py`（Apache-2.0，已落盘
`dataset/v2/official_repo/`）。移植目的：评测复现时不再依赖官方 repo 路径，
且能对 `eval_function` 带参串（如 `norm_phrase_set_match|lower=true|...`）做解析。

未移植：LLM judge（`llm_gotchas_checker` / `llm_abstention_checker`）——
它们需要 judge 端点与冻结 prompt，M1 只做确定性判分。
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable, List, Sequence

DEFAULT_SEPARATORS: Sequence[str] = (",", ";")


def normalize_phrase(
    text: str | None,
    *,
    lower: bool = True,
    normalize_hyphen: bool = True,
    strip_punct: bool = True,
) -> str:
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if lower:
        text = text.lower()
    if normalize_hyphen:
        text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"[,;]", " ", text)
    if strip_punct:
        text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_phrases(
    text: str | None,
    *,
    separators: Iterable[str] = DEFAULT_SEPARATORS,
    **normalize_kwargs: bool,
) -> List[str]:
    if text is None:
        return []
    separator_list = list(separators)
    if not separator_list:
        normalized = normalize_phrase(text, **normalize_kwargs)
        return [normalized] if normalized else []
    pattern = "|".join(re.escape(sep) for sep in separator_list)
    parts = re.split(pattern, text)
    normalized_parts = [normalize_phrase(part, **normalize_kwargs) for part in parts]
    return [part for part in normalized_parts if part]


def norm_phrase_set_match(
    prediction: str | None,
    answer: str | None,
    *,
    separators: Iterable[str] = DEFAULT_SEPARATORS,
    require_non_empty: bool = True,
    **normalize_kwargs: bool,
) -> bool:
    normalized_pred = normalize_phrase(prediction, **normalize_kwargs)
    answer_phrases = split_phrases(answer, separators=separators, **normalize_kwargs)
    if require_non_empty and (not normalized_pred or not answer_phrases):
        return False
    for phrase in set(answer_phrases):
        pattern = r"\b%s\b" % re.escape(phrase)
        if re.search(pattern, normalized_pred) is None:
            return False
    return True


def norm_phrase_set_match_ordered(
    prediction: str | None,
    answer: str | None,
    *,
    separators: Iterable[str] = DEFAULT_SEPARATORS,
    require_non_empty: bool = True,
    **normalize_kwargs: bool,
) -> bool:
    normalized_pred = normalize_phrase(prediction, **normalize_kwargs)
    answer_phrases = split_phrases(answer, separators=separators, **normalize_kwargs)
    if require_non_empty and (not normalized_pred or not answer_phrases):
        return False
    start = 0
    for phrase in answer_phrases:
        pattern = r"\b%s\b" % re.escape(phrase)
        match = re.search(pattern, normalized_pred[start:])
        if match is None:
            return False
        start += match.end()
    return True


def mc_choice_match(
    prediction: str | None,
    answer: str | None,
    *,
    strip_chars: str = ".",
    require_non_empty: bool = True,
    **_: Any,
) -> bool:
    if prediction is None or answer is None:
        return False
    if not isinstance(prediction, str):
        prediction = str(prediction)
    if not isinstance(answer, str):
        answer = str(answer)
    boxed_match = re.search(r"\\boxed\{([^}]*)\}", prediction.lower())
    candidate = boxed_match.group(1) if boxed_match else prediction
    cleaned = re.sub(r"\b(choice|option)\b", "", candidate, flags=re.IGNORECASE)
    for ch in strip_chars:
        cleaned = cleaned.replace(ch, "")
    cleaned = cleaned.strip().upper()
    expected = answer.strip().upper()
    if require_non_empty and (not cleaned or not expected):
        return False
    return cleaned == expected


_MULTI_SELECT_FILLER_WORDS = {
    "AND", "ANSWER", "ANSWERS", "CHOICE", "CHOICES", "FINAL", "LETTER", "LETTERS", "OPTION", "OPTIONS",
}


def _extract_multi_select_letters(text: str | None) -> list[str]:
    if text is None:
        return []
    if not isinstance(text, str):
        text = str(text)
    chunks = re.findall(r"[A-Z]+", text.upper())
    letters: list[str] = []
    for chunk in chunks:
        if chunk in _MULTI_SELECT_FILLER_WORDS:
            continue
        letters.extend(list(chunk))
    return letters


def mc_choice_set_match(
    prediction: str | None,
    answer: str | None,
    *,
    require_non_empty: bool = True,
    **_: Any,
) -> bool:
    pred_letters = _extract_multi_select_letters(prediction)
    answer_letters = _extract_multi_select_letters(answer)
    if require_non_empty and (not pred_letters or not answer_letters):
        return False
    return set(pred_letters) == set(answer_letters)


def extract_boxed_answer(text: str) -> str:
    marker = "\\boxed{"
    idx = text.rfind(marker)
    if idx == -1:
        return text.strip()
    i = idx + len(marker)
    depth = 1
    out: list[str] = []
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _parse_eval_value(key: str, value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"none", "null"}:
        return None
    if key in {"separators", "separator"}:
        if not value:
            return []
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return json.loads(stripped)
        return [ch for ch in value if not ch.isspace()]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


DETERMINISTIC_FUNCS: dict[str, Callable[..., Any]] = {
    "norm_phrase_set_match": norm_phrase_set_match,
    "norm_phrase_set_match_ordered": norm_phrase_set_match_ordered,
    "mc_choice_match": mc_choice_match,
    "mc_choice_set_match": mc_choice_set_match,
}

LLM_JUDGE_FUNCS = {"llm_gotchas_checker", "llm_abstention_checker"}


def parse_eval_function_spec(spec: str) -> tuple[str, dict[str, Any]]:
    parts = [part.strip() for part in spec.split("|")]
    name = parts[0]
    if not name:
        raise ValueError("eval function spec missing function name.")
    kwargs: dict[str, Any] = {}
    for part in parts[1:]:
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid eval function option: {part}")
        key, value = part.split("=", 1)
        kwargs[key.strip()] = _parse_eval_value(key.strip(), value.strip())
    return name, kwargs


def score_deterministic(prediction: str | None, answer: str | None, spec: str) -> bool | None:
    """返回 True/False；若是 LLM judge 函数则返回 None（需要 judge 端点）。

    判分前**先提取 `\\boxed{}` 内容**（与官方 harness 一致）。官方之所以能匹配
    `\\boxed{New Customers}`，是因为 harness 在判分前调用了 `extract_boxed_answer`；
    否则 normalize 会把 `\\boxed{` 与 `{` 删掉，变成 `boxednew customers`。
    另外剥离 `\\text{...}` 包装（DeepSeek 等模型常输出 `\\boxed{\\text{Submit}}`）。
    """
    name, kwargs = parse_eval_function_spec(spec)
    if name in LLM_JUDGE_FUNCS:
        return None
    func = DETERMINISTIC_FUNCS.get(name)
    if func is None:
        raise ValueError(f"unknown eval function: {name}")
    if isinstance(prediction, str):
        candidate = extract_boxed_answer(prediction)
        candidate = re.sub(r"\\text\{([^}]*)\}", r"\1", candidate)
        prediction = candidate
    return bool(func(prediction, answer, **kwargs))
