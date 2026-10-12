"""
Live, non-mocked verification run against the real OpenSanctions, Tavily,
and Indian Kanoon APIs.

Unlike evals/ (which mocks the HTTP layer against saved fixtures), this
script calls the real APIs with real names, to prove the pipeline surfaces
genuine evidence rather than a fabricated format check. Two name sets:

- RED_FLAG_CASES: real, publicly documented cases a compliance screen
  should catch (a UN/OFAC-sanctioned individual, a convicted-in-absentia
  fraud case with heavy mainstream press coverage). These are matters of
  public record, used here only to prove detection works.
- CLEAN_CASES: a legitimate, unremarkable company name to prove the same
  pipeline doesn't just always return red — the "nothing found" path has
  to be real too.

Every record returned is dumped to a timestamped JSON file under
verification_runs/ so a run isn't lost the moment the terminal closes.
"""
import json
from datetime import datetime
from pathlib import Path

from tools.indian_kanoon import ecourts_case_search
from tools.opensanctions import sanctions_pep_screen
from tools.tavily_search import adverse_media_search

RUNS_DIR = Path(__file__).parent.parent / "verification_runs"

RED_FLAG_CASES = [
    "Vladimir Putin",  # UN/EU/OFAC sanctioned — for OpenSanctions
    "Nirav Modi",  # convicted in absentia, PNB fraud case — for Tavily
]

CLEAN_CASES = [
    "Zoho Corporation",
]


def _load_env(path: str = ".env") -> dict:
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def main() -> None:
    env = _load_env()
    opensanctions_key = env["OPENSANCTIONS_API"]
    tavily_key = env["TAVILY_API_KEY"]
    indian_kanoon_key = env["INDIAN_KANOON_API"]

    results = {"run_at": datetime.now().isoformat(), "sanctions": [], "adverse_media": [], "litigation": []}

    print("=== OpenSanctions (real sanctioned name expected to hit) ===")
    for name in RED_FLAG_CASES + CLEAN_CASES:
        record = sanctions_pep_screen(
            vendor_id=f"verify-{name}", name=name, pan="AAAAA1111A", api_key=opensanctions_key
        )
        print(f"[{record.tag.value:>18}] {name}: {record.summary}")
        results["sanctions"].append(json.loads(record.model_dump_json()))

    print("\n=== Tavily adverse media (real fraud case expected to hit) ===")
    for name in RED_FLAG_CASES + CLEAN_CASES:
        record = adverse_media_search(vendor_id=f"verify-{name}", name=name, api_key=tavily_key)
        print(f"[{record.tag.value:>18}] {name}: {record.summary}")
        results["adverse_media"].append(json.loads(record.model_dump_json()))

    print("\n=== Indian Kanoon cheque-bounce search ===")
    for name in RED_FLAG_CASES + CLEAN_CASES:
        docs = ecourts_case_search(name=name, api_key=indian_kanoon_key)
        print(f"[{'hits=' + str(len(docs)):>18}] {name}: {[d.get('title') for d in docs[:2]]}")
        results["litigation"].append({"name": name, "hit_count": len(docs), "titles": [d.get("title") for d in docs[:3]]})

    RUNS_DIR.mkdir(exist_ok=True)
    out_path = RUNS_DIR / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved full run to {out_path}")


if __name__ == "__main__":
    main()
