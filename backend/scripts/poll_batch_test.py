"""Poll test batch jobs and display results when completed.

Usage: python -m scripts.poll_batch_test [--interval 60]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contextlib

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

    while True:
        all_done = True
        for _label, name in JOBS:
            job = client.batches.get(name=name)
            state = str(job.state).split(".")[-1]

            if state == "JOB_STATE_SUCCEEDED":
                if job.dest and job.dest.file_name:
                    content = client.files.download(file=job.dest.file_name)
                    data = content.decode()
                    # Parse and show first entry
                    for line in data.strip().split("\n"):
                        entry = json.loads(line)
                        entry.get("key", "?")
                        resp = entry.get("response", {})
                        cands = resp.get("candidates", [])
                        if cands:
                            text = cands[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            with contextlib.suppress(json.JSONDecodeError):
                                json.loads(text)
                        else:
                            pass
                elif job.dest and job.dest.inlined_responses:
                    pass
                else:
                    pass
            elif state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
                pass
            else:
                all_done = False

        if all_done:
            break

        time.sleep(interval)


if __name__ == "__main__":
    main()
