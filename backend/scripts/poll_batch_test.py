"""Poll test batch jobs and display results when completed.

Usage: python -m scripts.poll_batch_test [--interval 60]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google import genai


def main():
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 60

    # Read API key from .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    api_key = ""
    with open(env_path) as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.strip().split("=", 1)[1]
                break

    client = genai.Client(api_key=api_key)

    # Test jobs from E2E smoke test (2026-03-24)
    JOBS = [
        ("full-prod", "batches/o32i14cuv3s0x0y3yowppzfroqx5sb91b0a3"),
        ("basic-pdf", "batches/ppby62zjzrwo0l1xdkthb3c3ipedxk1krr6t"),
    ]

    print(f"Polling {len(JOBS)} batch jobs every {interval}s...")
    while True:
        all_done = True
        for label, name in JOBS:
            job = client.batches.get(name=name)
            state = str(job.state).split(".")[-1]
            print(f"  {label}: {state}", end="")

            if state == "JOB_STATE_SUCCEEDED":
                if job.dest and job.dest.file_name:
                    content = client.files.download(file=job.dest.file_name)
                    data = content.decode()
                    print(f"\n    Result ({len(data)} bytes):")
                    # Parse and show first entry
                    for line in data.strip().split("\n"):
                        entry = json.loads(line)
                        key = entry.get("key", "?")
                        resp = entry.get("response", {})
                        cands = resp.get("candidates", [])
                        if cands:
                            text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            try:
                                parsed = json.loads(text)
                                print(f"    key={key}, title={parsed.get('title', '?')}")
                                print(f"    citation={parsed.get('citation', '?')}")
                                print(f"    keys={list(parsed.keys())[:10]}...")
                            except json.JSONDecodeError:
                                print(f"    key={key}, raw_text={text[:200]}")
                        else:
                            print(f"    key={key}, no candidates")
                elif job.dest and job.dest.inlined_responses:
                    print(f"\n    {len(job.dest.inlined_responses)} inline responses")
                else:
                    print(f"\n    dest={job.dest}")
            elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
                print(f" ERROR: {job.error}")
            else:
                all_done = False
                print()

        if all_done:
            print("\nAll jobs completed!")
            break

        print(f"\nSleeping {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    main()
