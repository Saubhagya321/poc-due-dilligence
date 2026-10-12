"""
Seam under test: call_groq(messages, api_keys) — the public entry point every
agent will call for LLM inference.

We mock the low-level HTTP call here deliberately: the thing under test is
OUR rotation/retry logic, not Groq's live API behavior (that's already proven
working in test_apis.py against real keys, model openai/gpt-oss-120b). We
can't force a real 429 from Groq on demand without burning quota, so a
mocked 429 is the right way to exercise this specific branch.
"""
from tools.groq_client import GroqExhaustedError, call_groq


def test_rotates_to_the_next_key_when_the_first_is_rate_limited(mocker):
    responses = [
        RateLimitedResponse(),
        SuccessResponse("pong"),
    ]

    def fake_post(api_key, messages, model, max_tokens):
        return responses.pop(0)

    mocker.patch("tools.groq_client._post_chat_completion", side_effect=fake_post)

    reply = call_groq(
        messages=[{"role": "user", "content": "ping"}],
        api_keys=["key-1", "key-2", "key-3"],
    )

    assert reply == "pong"


def test_raises_only_after_every_key_is_rate_limited(mocker):
    mocker.patch(
        "tools.groq_client._post_chat_completion",
        side_effect=lambda api_key, messages, model, max_tokens: RateLimitedResponse(),
    )

    try:
        call_groq(
            messages=[{"role": "user", "content": "ping"}],
            api_keys=["key-1", "key-2"],
        )
        assert False, "expected GroqExhaustedError"
    except GroqExhaustedError as e:
        assert "2" in str(e)  # tried both keys


class RateLimitedResponse:
    is_rate_limited = True
    content = None


class SuccessResponse:
    is_rate_limited = False

    def __init__(self, content):
        self.content = content
