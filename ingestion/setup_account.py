"""Set up a single GCP account for turbo ingestion.

Run after logging in with `gcloud auth login` for the target account.

Usage:
    gcloud auth login                          # Log in via browser
    python ingestion/setup_account.py a        # Set up as Account A
    python ingestion/setup_account.py b        # Set up as Account B
    ...

What this script does:
1. Creates a GCP project (smriti-ingest-{letter})
2. Links billing account (free trial)
3. Enables Vertex AI API + Cloud Storage API
4. Creates service account with correct roles
5. Downloads service account JSON key
6. Creates GCS bucket for batch JSONL
7. Writes env_{letter} file
"""

import json
import os
import subprocess
import sys
from pathlib import Path

INGESTION_DIR = Path(__file__).resolve().parent
ACCOUNTS_DIR = INGESTION_DIR / "accounts"
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)


def run(cmd: str, check: bool = True, capture: bool = True) -> str:
    """Run a shell command and return stdout."""
    print(f"  $ {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True,
    )
    if check and result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        if "already exists" in result.stderr or "ALREADY_EXISTS" in result.stderr:
            print("  (Already exists — continuing)")
            return result.stdout.strip() if result.stdout else ""
        if "already enabled" in result.stderr:
            print("  (Already enabled — continuing)")
            return ""
        raise RuntimeError(f"Command failed: {cmd}\n{result.stderr}")
    return result.stdout.strip() if result.stdout else ""


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python ingestion/setup_account.py <letter>")
        print("  letter: a, b, c, or d")
        sys.exit(1)

    letter = sys.argv[1].lower()
    if letter not in ("a", "b", "c", "d"):
        print(f"Invalid letter: {letter}. Must be a, b, c, or d.")
        sys.exit(1)

    project_id = f"smriti-ingest-{letter}"
    bucket_name = f"smriti-batch-{letter}"
    sa_name = "smriti-ingestion"
    sa_email = f"{sa_name}@{project_id}.iam.gserviceaccount.com"
    key_path = ACCOUNTS_DIR / f"account_{letter}.json"
    env_path = ACCOUNTS_DIR / f"env_{letter}"

    print(f"\n{'='*60}")
    print(f"SETTING UP ACCOUNT {letter.upper()}")
    print(f"  Project: {project_id}")
    print(f"  Bucket:  {bucket_name}")
    print(f"  SA:      {sa_email}")
    print(f"{'='*60}\n")

    # Check who's logged in
    active = run("gcloud config get-value account")
    print(f"\nLogged in as: {active}\n")

    # Step 1: Create project
    print("--- Step 1: Create GCP Project ---")
    try:
        run(f'gcloud projects create {project_id} --name="Smriti Ingest {letter.upper()}"')
    except RuntimeError:
        print("  Project may already exist, continuing...")

    # Set as active project
    run(f"gcloud config set project {project_id}")

    # Step 2: Link billing account
    print("\n--- Step 2: Link Billing Account ---")
    billing_output = run("gcloud billing accounts list --format=json")
    billing_accounts = json.loads(billing_output) if billing_output else []

    if not billing_accounts:
        print("\n  WARNING: No billing accounts found!")
        print("  You need to enable billing manually:")
        print(f"  1. Go to: https://console.cloud.google.com/billing?project={project_id}")
        print("  2. Link the free trial billing account")
        print("  3. Re-run this script")
        input("  Press Enter after enabling billing...")
        billing_output = run("gcloud billing accounts list --format=json")
        billing_accounts = json.loads(billing_output) if billing_output else []

    if billing_accounts:
        # Use the first open billing account
        open_accounts = [b for b in billing_accounts if b.get("open", False)]
        if open_accounts:
            billing_id = open_accounts[0]["name"].split("/")[-1]
            print(f"  Using billing account: {billing_id}")
            try:
                run(f"gcloud billing projects link {project_id} --billing-account={billing_id}")
            except RuntimeError:
                print("  Billing link may already exist, continuing...")
        else:
            print("  WARNING: No open billing accounts. Enable free trial first.")

    # Step 3: Enable APIs
    print("\n--- Step 3: Enable APIs ---")
    for api in ["aiplatform.googleapis.com", "storage.googleapis.com"]:
        try:
            run(f"gcloud services enable {api} --project={project_id}")
        except RuntimeError:
            print(f"  {api} may already be enabled, continuing...")

    # Step 4: Create service account
    print("\n--- Step 4: Create Service Account ---")
    try:
        run(
            f'gcloud iam service-accounts create {sa_name} '
            f'--display-name="Smriti Ingestion" '
            f'--project={project_id}'
        )
    except RuntimeError:
        print("  Service account may already exist, continuing...")

    # Grant roles
    for role in ["roles/aiplatform.user", "roles/storage.admin"]:
        try:
            run(
                f"gcloud projects add-iam-policy-binding {project_id} "
                f"--member=serviceAccount:{sa_email} "
                f"--role={role} "
                f"--condition=None "
                f"--quiet"
            )
        except RuntimeError:
            print(f"  Role {role} may already be assigned, continuing...")

    # Step 5: Download service account key
    print(f"\n--- Step 5: Download Service Account Key → {key_path} ---")
    if key_path.exists():
        print(f"  Key already exists at {key_path}, skipping download.")
        print(f"  Delete it first if you want a fresh key.")
    else:
        run(
            f"gcloud iam service-accounts keys create {key_path} "
            f"--iam-account={sa_email} "
            f"--project={project_id}"
        )
        print(f"  Key saved to {key_path}")

    # Step 6: Create GCS bucket
    print(f"\n--- Step 6: Create GCS Bucket: {bucket_name} ---")
    try:
        run(
            f"gcloud storage buckets create gs://{bucket_name} "
            f"--project={project_id} "
            f"--location=us-central1 "
            f"--uniform-bucket-level-access"
        )
    except RuntimeError:
        print("  Bucket may already exist, continuing...")

    # Step 7: Write env file
    print(f"\n--- Step 7: Write env file → {env_path} ---")

    # Read shared credentials from existing env_template or backend/.env
    backend_env = INGESTION_DIR.parent / "backend" / ".env"
    shared_vars = {}
    if backend_env.exists():
        with open(backend_env, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    if k in (
                        "DATABASE_URL", "PINECONE_API_KEY", "PINECONE_HOST",
                        "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD",
                        "GCS_PDF_BUCKET",
                    ):
                        shared_vars[k] = v.strip()

    env_content = f"""# Turbo Ingestion - Account {letter.upper()}
# Auto-generated by setup_account.py

# === PER-ACCOUNT ===
GEMINI_USE_VERTEXAI=true
GEMINI_VERTEXAI_PROJECT={project_id}
GEMINI_VERTEXAI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=ingestion/accounts/account_{letter}.json
GCS_BUCKET={bucket_name}

# === STORAGE ===
STORAGE_PROVIDER=local
GCS_PDF_BUCKET={shared_vars.get('GCS_PDF_BUCKET', 'smriti-production-documents')}

# === SHARED DB CREDENTIALS ===
DATABASE_URL={shared_vars.get('DATABASE_URL', 'FILL_IN')}
PINECONE_API_KEY={shared_vars.get('PINECONE_API_KEY', 'FILL_IN')}
PINECONE_HOST={shared_vars.get('PINECONE_HOST', 'FILL_IN')}
NEO4J_URI={shared_vars.get('NEO4J_URI', 'FILL_IN')}
NEO4J_USER={shared_vars.get('NEO4J_USER', 'FILL_IN')}
NEO4J_PASSWORD={shared_vars.get('NEO4J_PASSWORD', 'FILL_IN')}
"""

    env_path.write_text(env_content, encoding="utf-8")
    print(f"  Env file written to {env_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"ACCOUNT {letter.upper()} SETUP COMPLETE")
    print(f"  Project:  {project_id}")
    print(f"  Bucket:   gs://{bucket_name}")
    print(f"  SA Key:   {key_path}")
    print(f"  Env file: {env_path}")
    print(f"{'='*60}")
    print(f"\nNext: Log in as the next Gmail account and run:")
    next_letters = {"a": "b", "b": "c", "c": "d", "d": "done"}
    nl = next_letters[letter]
    if nl != "done":
        print(f"  gcloud auth login")
        print(f"  python ingestion/setup_account.py {nl}")
    else:
        print(f"  All accounts set up! Run: python ingestion/turbo_ingest.py --setup")


if __name__ == "__main__":
    main()
