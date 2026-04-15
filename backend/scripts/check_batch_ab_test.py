"""Poll batch A/B test job and compare results with online baseline."""
import json
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = (
    r"C:\Users\yadav\OneDrive - UPES\Desktop"
    r"\project-9642efb2-7b75-4a7d-811-90cc98bacc13.json"
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
    print(f"State: {batch.state}")
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
        "title", "citation", "court", "year", "decision_date",
        "judge", "author_judge", "case_type", "case_number",
    ]
    QUALITY_FIELDS = [
        "ratio_decidendi", "acts_cited", "cases_cited", "keywords",
        "disposal_nature", "bench_type", "jurisdiction",
        "petitioner", "respondent", "is_reportable",
    ]
    V3_FIELDS = [
        "legal_propositions", "headnotes", "outcome_summary",
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
                print(f"  Batch item {i}: NO CANDIDATES (may have failed)")
                continue
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"  Batch item {i}: PARSE ERROR: {e}")
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
            print(f"\n  Batch item {i} ({batch_title[:50]}): NO ONLINE MATCH")
            continue

        fname, online_data = matched_online
        print(f"\n{'='*70}")
        print(f"CASE: {fname}")
        print(f"{'='*70}")

        # Compare critical fields
        print("\n--- CRITICAL FIELDS ---")
        for field in CRITICAL_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            match = "MATCH" if str(o) == str(b) else "DIFF"
            if match == "DIFF":
                print(f"  {field}: {match}")
                print(f"    Online: {str(o)[:100]}")
                print(f"    Batch:  {str(b)[:100]}")
            else:
                print(f"  {field}: MATCH ✓")

        # Compare quality fields
        print("\n--- QUALITY FIELDS ---")
        for field in QUALITY_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            if isinstance(o, list) and isinstance(b, list):
                o_count, b_count = len(o), len(b)
                overlap = len(set(str(x) for x in o) & set(str(x) for x in b))
                print(f"  {field}: online={o_count}, batch={b_count}, overlap={overlap}")
            elif isinstance(o, str) and isinstance(b, str):
                # Compare string length as proxy for completeness
                o_len, b_len = len(o), len(b)
                print(f"  {field}: online={o_len}chars, batch={b_len}chars")
            else:
                match = "MATCH" if str(o) == str(b) else "DIFF"
                if match == "DIFF":
                    print(f"  {field}: Online={o}, Batch={b}")
                else:
                    print(f"  {field}: MATCH ✓")

        # Compare V3 fields
        print("\n--- V3 FIELDS (research agent critical) ---")
        for field in V3_FIELDS:
            o = online_data.get(field)
            b = batch_data.get(field)
            if isinstance(o, list) and isinstance(b, list):
                print(f"  {field}: online={len(o)} items, batch={len(b)} items")
                # Show first proposition from each
                if o and isinstance(o[0], dict):
                    key = "proposition_text" if "proposition_text" in o[0] else "proposition"
                    if key in o[0]:
                        print(f"    Online[0]: {str(o[0].get(key, ''))[:100]}")
                    if b and isinstance(b[0], dict) and key in b[0]:
                        print(f"    Batch[0]:  {str(b[0].get(key, ''))[:100]}")
            elif isinstance(o, str) and isinstance(b, str):
                print(f"  {field}: online={len(o)}chars, batch={len(b)}chars")
            else:
                print(f"  {field}: Online={type(o).__name__}, Batch={type(b).__name__}")

        # Overall score
        online_filled = sum(
            1 for v in online_data.values()
            if v is not None and v != [] and v != ""
        )
        batch_filled = sum(
            1 for v in batch_data.values()
            if v is not None and v != [] and v != ""
        )
        print(f"\n  FIELD FILL: online={online_filled}, batch={batch_filled}")


if __name__ == "__main__":
    batch = check_status()
    state_str = str(batch.state)

    if "SUCCEEDED" in state_str or "COMPLETED" in state_str:
        print("\nBatch COMPLETED! Downloading results...\n")
        results = download_results()
        print(f"Got {len(results)} batch results\n")
        compare("backend/data/ab_test_online.json", results)
    elif "FAILED" in state_str or "CANCELLED" in state_str:
        print(f"\nBatch FAILED: {batch.state}")
        if hasattr(batch, "error"):
            print(f"Error: {batch.error}")
    else:
        print(f"\nBatch still running ({batch.state}). Re-run this script to check again.")
