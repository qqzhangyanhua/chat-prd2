from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


logger = logging.getLogger(__name__)


class ModelGatewayError(Exception):
    """模型网关统一异常。"""


class StaticReplyStream:
    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    def __iter__(self) -> Iterator[str]:
        yield from self._chunks

    def close(self) -> None:
        return None


class GatewayReplyStream:
    def __init__(self, client: httpx.Client, response: httpx.Response, url: str):
        self._client = client
        self._response = response
        self._url = url
        self._closed = False

    def __iter__(self) -> Iterator[str]:
        saw_delta = False

        try:
            for raw_line in self._response.iter_lines():
                line = raw_line.strip()
                if not line or not line.startswith("data:"):
                    continue

                payload = line.removeprefix("data:").strip()
                if payload == "[DONE]":
                    break

                try:
                    body = json.loads(payload)
                except ValueError as exc:
                    logger.warning(
                        "上游模型流式响应不是合法 JSON: url=%s payload_preview=%s",
                        self._url,
                        _preview_text(payload),
                    )
                    raise ModelGatewayError("上游流式响应格式不兼容") from exc

                delta = _extract_stream_delta(body)
                if not delta:
                    continue

                saw_delta = True
                yield delta
        finally:
            self.close()

        if not saw_delta:
            logger.warning("上游模型流式响应没有可用文本: url=%s", self._url)
            raise ModelGatewayError("上游响应没有可用文本")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._response.close()
        self._client.close()


def _build_chat_completions_url(base_url: str) -> str:
    parsed = urlsplit(base_url.strip())
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        normalized_path = path
    elif not path:
        normalized_path = "/v1/chat/completions"
    else:
        normalized_path = f"{path}/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, normalized_path, parsed.query, parsed.fragment))


def _preview_text(raw: str, limit: int = 300) -> str:
    normalized = " ".join(raw.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def _preview_body(body: Any, limit: int = 300) -> str:
    if isinstance(body, str):
        return _preview_text(body, limit)

    try:
        serialized = json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        serialized = repr(body)
    return _preview_text(serialized, limit)


def _extract_text_content(content: Any) -> str | None:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        pieces: list[str] = []
        for item in content:
            if isinstance(item, str):
                pieces.append(item)
                continue

            if not isinstance(item, dict):
                continue

            text = item.get("text")
            if isinstance(text, str):
                pieces.append(text)
                continue

            if isinstance(text, dict) and isinstance(text.get("value"), str):
                pieces.append(text["value"])

        if pieces:
            return "".join(pieces)

    return None


def _extract_chat_completion_content(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None

    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None

    return _extract_text_content(message.get("content"))


def _extract_json_object_content(body: Any) -> dict[str, Any]:
    content = _extract_chat_completion_content(body)
    if not isinstance(content, str):
        logger.warning("上游结构化提取响应结构不兼容: body_preview=%s", _preview_body(body))
        raise ModelGatewayError("上游结构化提取响应格式不兼容")

    try:
        parsed = json.loads(content)
    except ValueError as exc:
        logger.warning("上游结构化提取结果不是合法 JSON: content_preview=%s", _preview_text(content))
        raise ModelGatewayError("上游结构化提取结果不是合法 JSON") from exc

    if not isinstance(parsed, dict):
        logger.warning("上游结构化提取结果不是对象: content_preview=%s", _preview_body(parsed))
        raise ModelGatewayError("上游结构化提取结果不是对象")

    return parsed


def _extract_stream_delta(body: Any) -> str:
    if not isinstance(body, dict):
        return ""

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        delta_text = _extract_text_content(delta.get("content"))
        if isinstance(delta_text, str):
            return delta_text

    message = first_choice.get("message")
    if isinstance(message, dict):
        message_text = _extract_text_content(message.get("content"))
        if isinstance(message_text, str):
            return message_text

    return ""


def _build_stream_payload(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model": model,
        "messages": messages,
        "stream": True,
    }


def _raise_for_gateway_http_error(exc: httpx.HTTPStatusError, url: str) -> None:
    status_code = exc.response.status_code if exc.response else "unknown"
    response_preview = ""
    content_type = "unknown"
    if exc.response is not None:
        response_preview = _preview_text(exc.response.text)
        content_type = exc.response.headers.get("content-type", "unknown")
    logger.warning(
        "上游模型 HTTP 错误: url=%s status=%s content_type=%s body_preview=%s",
        url,
        status_code,
        content_type,
        response_preview,
    )
    raise ModelGatewayError(f"上游 HTTP 错误: {status_code}") from exc


def _raise_for_non_json_response(response: httpx.Response, url: str, exc: ValueError) -> None:
    logger.warning(
        "上游模型返回非 JSON 响应: url=%s status=%s content_type=%s body_preview=%s",
        url,
        response.status_code,
        response.headers.get("content-type", "unknown"),
        _preview_text(response.text),
    )
    raise ModelGatewayError("上游返回非 JSON 响应，请检查 base_url 是否指向 OpenAI 兼容接口") from exc


def open_reply_stream(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
) -> GatewayReplyStream | StaticReplyStream:
    url = _build_chat_completions_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    client = httpx.Client(timeout=30.0)
    request = client.build_request("POST", url, headers=headers, json=_build_stream_payload(model, messages))

    try:
        response = client.send(request, stream=True)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        client.close()
        _raise_for_gateway_http_error(exc, url)
    except httpx.TimeoutException as exc:
        client.close()
        logger.warning("调用上游模型超时: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游模型超时") from exc
    except httpx.RequestError as exc:
        client.close()
        logger.warning("调用上游模型网络异常: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游模型网络异常") from exc

    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type:
        return GatewayReplyStream(client, response, url)

    try:
        body = response.json()
    except ValueError as exc:
        response.close()
        client.close()
        _raise_for_non_json_response(response, url, exc)

    response.close()
    client.close()

    content = _extract_chat_completion_content(body)
    if not isinstance(content, str):
        logger.warning(
            "上游模型响应结构不兼容: url=%s status=%s body_preview=%s",
            url,
            response.status_code,
            _preview_body(body),
        )
        raise ModelGatewayError("上游响应格式不兼容")

    if not content.strip():
        logger.warning(
            "上游模型响应没有可用文本: url=%s content_type=%s content_preview=%s",
            url,
            type(content).__name__,
            _preview_body(content),
        )
        raise ModelGatewayError("上游响应没有可用文本")

    return StaticReplyStream([content])


def generate_reply(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
) -> str:
    url = _build_chat_completions_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _raise_for_gateway_http_error(exc, url)
    except httpx.TimeoutException as exc:
        logger.warning("调用上游模型超时: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游模型超时") from exc
    except httpx.RequestError as exc:
        logger.warning("调用上游模型网络异常: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游模型网络异常") from exc

    try:
        body = response.json()
    except ValueError as exc:
        _raise_for_non_json_response(response, url, exc)

    content = _extract_chat_completion_content(body)
    if not isinstance(content, str):
        logger.warning(
            "上游模型响应结构不兼容: url=%s status=%s body_preview=%s",
            url,
            response.status_code,
            _preview_body(body),
        )
        raise ModelGatewayError("上游响应格式不兼容")

    if not content.strip():
        logger.warning(
            "上游模型响应没有可用文本: url=%s content_type=%s content_preview=%s",
            url,
            type(content).__name__,
            _preview_body(content),
        )
        raise ModelGatewayError("上游响应没有可用文本")

    return content


def generate_structured_extraction(
    base_url: str,
    api_key: str,
    model: str,
    state: dict[str, Any],
    target_section: str | None,
    user_input: str,
) -> dict[str, Any]:
    url = _build_chat_completions_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是 PRD 结构化提取器。"
                "你只能返回 JSON object。"
                "输出字段只允许 should_update、confidence、reasoning_summary、state_patch、prd_patch。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "state": state,
                    "target_section": target_section,
                    "user_input": user_input,
                },
                ensure_ascii=False,
            ),
        },
    ]
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _raise_for_gateway_http_error(exc, url)
    except httpx.TimeoutException as exc:
        logger.warning("调用上游结构化提取超时: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游结构化提取超时") from exc
    except httpx.RequestError as exc:
        logger.warning("调用上游结构化提取网络异常: url=%s error=%s", url, exc)
        raise ModelGatewayError("调用上游结构化提取网络异常") from exc

    try:
        body = response.json()
    except ValueError as exc:
        _raise_for_non_json_response(response, url, exc)

    return _extract_json_object_content(body)
