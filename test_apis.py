import json
import urllib.request
import urllib.parse
import urllib.error


def load_env(path=".env"):
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _post_json(url, payload, headers, timeout=20):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_opensanctions(api_key):
    print("\n--- OpenSanctions ---")
    try:
        status, body = _post_json(
            "https://api.opensanctions.org/match/default",
            {"queries": {"q1": {"schema": "Person", "properties": {"name": ["Vladimir Putin"]}}}},
            {"Content-Type": "application/json", "Authorization": f"ApiKey {api_key}"},
        )
        results = body.get("responses", {}).get("q1", {}).get("results", [])
        print(f"OK - status {status}, {len(results)} match(es); top: {results[0].get('caption') if results else '-'}")
    except urllib.error.HTTPError as e:
        print(f"FAILED - HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        print(f"FAILED - {type(e).__name__}: {e}")


def test_indian_kanoon(api_key):
    print("\n--- Indian Kanoon ---")
    url = "https://api.indiankanoon.org/search/?formInput=" + urllib.parse.quote("cheque bounce")
    req = urllib.request.Request(url, data=b"", method="POST")
    req.add_header("Authorization", f"Token {api_key}")
    req.add_header("User-Agent", "Mozilla/5.0 poc-due-diligence/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"OK - status {resp.status}, found={body.get('found')}, {len(body.get('docs', []))} doc(s)")
    except urllib.error.HTTPError as e:
        print(f"FAILED - HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        print(f"FAILED - {type(e).__name__}: {e}")


def test_groq(key_name, api_key):
    print(f"\n--- Groq: {key_name} ---")
    try:
        status, body = _post_json(
            "https://api.groq.com/openai/v1/chat/completions",
            {
                "model": "openai/gpt-oss-20b",
                "messages": [{"role": "user", "content": "Reply with just the word: pong"}],
                "max_tokens": 5,
            },
            {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        content = body["choices"][0]["message"]["content"].strip()
        print(f"OK - status {status}, reply: {content!r}")
    except urllib.error.HTTPError as e:
        print(f"FAILED - HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        print(f"FAILED - {type(e).__name__}: {e}")


def test_tavily(api_key):
    print("\n--- Tavily ---")
    try:
        status, body = _post_json(
            "https://api.tavily.com/search",
            {"api_key": api_key, "query": "OpenSanctions sanctions PEP", "max_results": 2},
            {"Content-Type": "application/json"},
        )
        results = body.get("results", [])
        print(f"OK - status {status}, {len(results)} result(s); first: {results[0].get('title') if results else '-'}")
    except urllib.error.HTTPError as e:
        print(f"FAILED - HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}")
    except Exception as e:
        print(f"FAILED - {type(e).__name__}: {e}")


if __name__ == "__main__":
    env = load_env()

    if env.get("OPENSANCTIONS_API"):
        test_opensanctions(env["OPENSANCTIONS_API"])
    if env.get("INDIAN_KANOON_API"):
        test_indian_kanoon(env["INDIAN_KANOON_API"])
    if env.get("TAVILY_API_KEY"):
        test_tavily(env["TAVILY_API_KEY"])

    for i in range(1, 6):
        k = f"GROQ_API_KEY_{i}"
        if env.get(k):
            test_groq(k, env[k])
