"""Poll batch A/B test job and compare results with online baseline."""

import json
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
    r"C:\Users\yadav\OneDrive - UPES\Desktop" r"\project-9642efb2-7b75-4a7d-811-90cc98bacc13.json"
)

from google import genai
from google.cloud import storage as gcs_storage

PROJECT = "project-9642efb2-7b75-4a7d-811"
BATCH_NAME = "projects/964182959084/locations/us-central1/batchPredictionJobs/1264453335608459264"

client = genai.Client(vertexai=True, project=PROJECT, location="us-central1")
gcs = gcs_storage.Client(project=PROJECT)
bucket = gcs.bucket("smriti-batch-ingestion")


def check_status():
    batch = client.batches.get(name=BATCH_NAME)
    return batch


def download_results():
    """Download batch output JSONL from GCS."""
    blobs = list(bucket.list_blobs(prefix="ab-test/output/"))
    results = []
    for blob in blobs:
        if blob.name.endswith(".jsonl"):
            content = blob.download_as_text()
            for line in content.strip().split("\n"):
                if line.strip():
                    results.append(json.loads(line))
    return results


def compare(online_path, batch_results):
    """Compare online vs batch extraction quality."""
    with open(online_path) as f:
        online = json.load(f)

    # Key fields to compare
    CRITICAL_FIELDS = [
        "title",
        "citation",
        "court",
        "year",
        "decision_date",
        "judge",
        "author_judge",
        "case_type",
        "case_number",
    ]
    QUALITY_FIELDS = [
        "ratio_decidendi",
        "acts_cited",
        "cases_cited",
        "keywords",
        "disposal_nature",
        "bench_type",
        "jurisdiction",
        "petitioner",
        "respondent",
        "is_reportable",
    ]
    V3_FIELDS = [
        "legal_propositions",
        "headnotes",
        "outcome_summary",
    ]

    for i, batch_item in enumerate(batch_results):
        # Extract the response text from batch output
        try:
            response = batch_item.get("response", {})
            candidates = response.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
                batch_data = json.loads(text)
            else:
                continue
        except (json.JSONDecodeError, KeyError, IndexError):
            continue

        # Try to match with online result by title
        batch_title = batch_data.get("title", "")
        matched_online = None
        for fname, odata in online.items():
            if odata.get("title", "").lower()[:30] == batch_title.lower()[:30]:
                matched_online = (fname, odata)
                break

        if not matched_online:
            # Match by index
            fnames = list(online.keys())
            if i < len(fnames):
                matched_online = (fnames[i], online[fnames[i]])

        if not matched_online:
            continue

        fname, online_data = matched_online

        # Compare critical fields
        for field in CRITICAL_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            match = "MATCH" if str(o) == str(b) else "DIFF"
            if match == "DIFF":
                pass
            else:
                pass

        # Compare quality fields
        for field in QUALITY_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            if isinstance(o, list) and isinstance(b, list):
                _o_count, _b_count = len(o), len(b)
                len(set(str(x) for x in o) & set(str(x) for x in b))
            elif isinstance(o, str) and isinstance(b, str):
                # Compare string length as proxy for completeness
                _o_len, _b_len = len(o), len(b)
            else:
                match = "MATCH" if str(o) == str(b) else "DIFF"
                if match == "DIFF":
                    pass
                else:
                    pass

        # Compare V3 fields
        for field in V3_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            if isinstance(o, list) and isinstance(b, list):
                # Show first proposition from each
                if o and isinstance(o[0], dict):
                    key = "proposition_text" if "proposition_text" in o[0] else "proposition"
                    if key in o[0]:
                        pass
                    if b and isinstance(b[0], dict) and key in b[0]:
                        pass
            elif isinstance(o, str) and isinstance(b, str):
                pass
            else:
                pass

        # Overall score
        sum(1 for v in online_data.values() if v is not None and v != [] and v != "")
        sum(1 for v in batch_data.values() if v is not None and v != [] and v != "")


if __name__ == "__main__":
    batch = check_status()
    state_str = str(batch.state)

    if "SUCCEEDED" in state_str or "COMPLETED" in state_str:
        results = download_results()
        compare("backend/data/ab_test_online.json", results)
    elif "FAILED" in state_str or "CANCELLED" in state_str:
        if hasattr(batch, "error"):
            pass
    else:
        pass
