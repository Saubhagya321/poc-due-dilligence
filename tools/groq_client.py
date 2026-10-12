import json
import urllib.error
import urllib.request

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqExhaustedError(RuntimeError):
    pass


class _ChatResponse:
    def __init__(self, is_rate_limited: bool, content: str | None):
        self.is_rate_limited = is_rate_limited
        self.content = content


def _post_chat_completion(api_key: str, messages: list[dict], model: str, max_tokens: int) -> _ChatResponse:
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GROQ_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            return _ChatResponse(is_rate_limited=False, content=content)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return _ChatResponse(is_rate_limited=True, content=None)
        raise


def call_groq(
    messages: list[dict],
    api_keys: list[str],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 512,
) -> str:
    """
    Calls Groq's chat completion endpoint, rotating to the next API key
    whenever the current one is rate-limited (HTTP 429). Raises
    GroqExhaustedError only once every key has been tried and rate-limited.

    gpt-oss models spend part of max_tokens on internal reasoning before
    emitting visible content — a low max_tokens (e.g. 50) can silently
    return an empty string with completion still "successful". Keep this
    generous for agents doing real reasoning, not just short replies.
    """
    for api_key in api_keys:
        response = _post_chat_completion(api_key, messages, model, max_tokens)
        if not response.is_rate_limited:
            return response.content

    raise GroqExhaustedError(f"All {len(api_keys)} Groq API keys are rate-limited")
