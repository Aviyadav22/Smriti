# COST RULES — READ BEFORE ANY API CALL

## ABSOLUTE RULE: NEVER USE AI STUDIO

**AI Studio (api_key-based) costs REAL MONEY from personal billing.**
**Vertex AI (service account-based) uses FREE $300 trial credits.**

### MANDATORY SETTINGS FOR ALL INGESTION
```bash
GEMINI_USE_VERTEXAI=true          # ALWAYS true — uses free trial credits
# NEVER set GEMINI_USE_VERTEXAI=false
# NEVER use GEMINI_API_KEY for any ingestion operation
# NEVER import genai.Client(api_key=...) for ingestion
```

### Why This Matters
- AI Studio API key = billed to personal Google account = REAL MONEY
- Vertex AI service account = billed to GCP project = FREE $300 trial credits
- The same model (gemini-2.5-flash, gemini-embedding-2-preview) is available on BOTH
- ALWAYS use Vertex AI path with service account credentials

### How To Verify
Before running ANY script, check:
1. `GEMINI_USE_VERTEXAI=true` in the env file
2. `GOOGLE_APPLICATION_CREDENTIALS` points to a service account JSON
3. NO reference to `GEMINI_API_KEY` or `api_key=` in the command

### If Vertex AI Returns 429 (Rate Limited)
- REDUCE concurrency (--concurrency 1)
- REDUCE RPM (--rpm-limit 5)
- WAIT and retry (quotas reset per minute)
- Request quota increase on GCP console
- NEVER switch to AI Studio as a "workaround"
