import httpx
import pytest

from app.services.model_gateway import ModelGatewayError, generate_reply


class DummyResponse:
    def __init__(self, payload, raise_error: Exception | None = None):
        self._payload = payload
        self._raise_error = raise_error

    def raise_for_status(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def json(self):
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
