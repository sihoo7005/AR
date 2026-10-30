import json
import re
import urllib.error
import urllib.request


class ChatError(Exception):
    def __init__(self, message, retryable=False, retry_after=0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def stream_chat(api_key, messages, model="openrouter/free", provider="openrouter"):
    """Stream only OpenRouter free models."""
    if provider == "groq":
        if model not in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            raise ChatError("지원하지 않는 Groq 모델입니다.")
        url = "https://api.groq.com/openai/v1/chat/completions"
    elif provider == "openrouter":
        url = "https://openrouter.ai/api/v1/chat/completions"
        if model != "openrouter/free" and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:free", model):
            raise ChatError("무료 모델 ID만 사용할 수 있습니다. (:free)")
    else:
        raise ChatError("지원하지 않는 제공업체입니다.")
    request = urllib.request.Request(
        url,
        data=json.dumps({"model": model, "messages": messages, "stream": True}).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "Free-AI-Router/0.1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            for line in response:
                line = line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                event = json.loads(data)
                if event.get("error"):
                    raise ChatError("제공업체가 응답 중 오류를 반환했습니다.")
                choices = event.get("choices") or []
                if choices:
                    content = choices[0].get("delta", {}).get("content")
                    if content:
                        yield content
            raise ChatError("응답이 완료되기 전에 연결이 종료되었습니다.")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            delay = min(int(retry_after), 86400) if retry_after.isdigit() else 60
            raise ChatError("사용 한도에 도달했습니다.", retryable=True, retry_after=delay) from exc
        if 500 <= exc.code <= 599:
            raise ChatError(f"서비스 장애 (HTTP {exc.code}).", retryable=True) from exc
        raise ChatError(f"API 요청 실패 (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ChatError("네트워크 연결에 실패했습니다. 나중에 다시 시도하세요.") from exc
    except (ValueError, UnicodeError, TypeError, KeyError) as exc:
        raise ChatError("API 응답을 읽을 수 없습니다.") from exc
