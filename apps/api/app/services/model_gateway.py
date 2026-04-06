from __future__ import annotations

from typing import Any

import httpx


class ModelGatewayError(Exception):
    """模型网关统一异常。"""


def _build_chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


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
        status_code = exc.response.status_code if exc.response else "unknown"
        raise ModelGatewayError(f"上游 HTTP 错误: {status_code}") from exc
    except httpx.TimeoutException as exc:
        raise ModelGatewayError("调用上游模型超时") from exc
    except httpx.RequestError as exc:
        raise ModelGatewayError("调用上游模型网络异常") from exc

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise ModelGatewayError("上游响应格式不兼容") from exc

    if not isinstance(content, str) or not content.strip():
        raise ModelGatewayError("上游响应没有可用文本")

    return content
