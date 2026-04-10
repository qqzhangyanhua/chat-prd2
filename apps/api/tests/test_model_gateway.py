import httpx
import pytest

from app.services.model_gateway import (
    ModelGatewayError,
    generate_reply,
    generate_structured_extraction,
)


class DummyResponse:
    def __init__(
        self,
        payload,
        raise_error: Exception | None = None,
        *,
        headers: dict[str, str] | None = None,
        status_code: int = 200,
        text: str | None = None,
        json_error: Exception | None = None,
    ):
        self._payload = payload
        self._raise_error = raise_error
        self.headers = headers or {"content-type": "application/json"}
        self.status_code = status_code
        self.text = text if text is not None else str(payload)
        self._json_error = json_error

    def raise_for_status(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


def test_generate_reply_success_and_request_payload(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "这是助手回复",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    messages = [{"role": "user", "content": "你好"}]
    result = generate_reply(
        base_url="https://api.example.com/v1/",
        api_key="secret-key",
        model="gpt-test",
        messages=messages,
    )

    assert result == "这是助手回复"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer secret-key",
        "Content-Type": "application/json",
    }
    assert captured["json"] == {"model": "gpt-test", "messages": messages}
    assert captured["timeout"] == 30.0


def test_generate_structured_extraction_success_and_request_payload(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"should_update":true,"confidence":"high","reasoning_summary":"识别到目标用户",'
                                '"state_patch":{"target_user":"独立开发者"},"prd_patch":{"target_user":{"title":"目标用户","content":"独立开发者","status":"confirmed"}}}'
                            ),
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = generate_structured_extraction(
        base_url="https://api.example.com/v1/",
        api_key="secret-key",
        model="gpt-test",
        state={"target_user": None},
        target_section="target_user",
        user_input="独立开发者",
    )

    assert result["should_update"] is True
    assert result["state_patch"]["target_user"] == "独立开发者"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer secret-key",
        "Content-Type": "application/json",
    }
    assert captured["json"]["model"] == "gpt-test"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 30.0


def test_generate_structured_extraction_raises_on_invalid_json_content(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "这不是 JSON",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError, match="上游结构化提取结果不是合法 JSON"):
        generate_structured_extraction(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="gpt-test",
            state={"target_user": None},
            target_section="target_user",
            user_input="独立开发者",
        )


def test_generate_reply_defaults_root_base_url_to_v1_path(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": "这是助手回复",
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = generate_reply(
        base_url="https://api.example.com",
        api_key="secret-key",
        model="gpt-test",
        messages=[{"role": "user", "content": "你好"}],
    )

    assert result == "这是助手回复"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"


def test_generate_reply_raises_model_gateway_error_on_http_status_error(monkeypatch):
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(502, request=request)

    def fake_post(url, *, headers, json, timeout):
        return DummyResponse(
            {},
            raise_error=httpx.HTTPStatusError(
                "bad gateway",
                request=request,
                response=response,
            ),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError):
        generate_reply(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="gpt-test",
            messages=[{"role": "user", "content": "hi"}],
        )


@pytest.mark.parametrize(
    "error",
    [
        httpx.TimeoutException("request timeout"),
        httpx.ConnectError(
            "network down",
            request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
        ),
    ],
)
def test_generate_reply_raises_model_gateway_error_on_timeout_or_network_error(
    monkeypatch, error
):
    def fake_post(url, *, headers, json, timeout):
        raise error

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError):
        generate_reply(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="gpt-test",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_generate_reply_logs_non_json_response_preview(monkeypatch, caplog):
    def fake_post(url, *, headers, json, timeout):
        return DummyResponse(
            None,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body>New API</body></html>",
            json_error=ValueError("not json"),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    with caplog.at_level("WARNING"):
        with pytest.raises(ModelGatewayError) as exc_info:
            generate_reply(
                base_url="https://api.example.com/v1",
                api_key="secret-key",
                model="gpt-test",
                messages=[{"role": "user", "content": "hi"}],
            )

    assert str(exc_info.value) == "上游返回非 JSON 响应，请检查 base_url 是否指向 OpenAI 兼容接口"
    assert "text/html; charset=utf-8" in caplog.text
    assert "New API" in caplog.text


def test_generate_reply_raises_model_gateway_error_on_incompatible_response(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        return DummyResponse({"choices": [{"message": {}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError):
        generate_reply(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="gpt-test",
            messages=[{"role": "user", "content": "hi"}],
        )


@pytest.mark.parametrize("content", ["", "   ", 123])
def test_generate_reply_raises_model_gateway_error_on_unusable_content(
    monkeypatch, content
):
    def fake_post(url, *, headers, json, timeout):
        return DummyResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError):
        generate_reply(
            base_url="https://api.example.com/v1",
            api_key="secret-key",
            model="gpt-test",
            messages=[{"role": "user", "content": "hi"}],
        )


def test_call_pm_mentor_llm_returns_parsed_dict(monkeypatch):
    import json
    from app.services.model_gateway import call_pm_mentor_llm

    fake_response_body = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "observation": "obs",
                    "challenge": "ch",
                    "suggestion": "sg",
                    "question": "q?",
                    "reply": "full reply",
                    "prd_updates": {},
                    "confidence": "medium",
                    "next_focus": "problem",
                })
            }
        }]
    }

    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        def raise_for_status(self): pass
        def json(self): return fake_response_body

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    result = call_pm_mentor_llm(
        base_url="http://fake-api",
        api_key="test-key",
        model="gpt-4",
        system_prompt="你是PM导师",
        user_prompt='{"user_input": "我想做个工具"}',
    )
    assert result["observation"] == "obs"
    assert result["confidence"] == "medium"
    assert captured.get("timeout") == 60.0
    payload = captured.get("json", {})
    assert payload.get("response_format") == {"type": "json_object"}


def test_call_pm_mentor_llm_raises_on_timeout(monkeypatch):
    from app.services.model_gateway import call_pm_mentor_llm

    def fake_post(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError, match="超时"):
        call_pm_mentor_llm(
            base_url="http://fake-api",
            api_key="key",
            model="gpt-4",
            system_prompt="sys",
            user_prompt="usr",
        )
