# Moving Smriti off GCP onto the Hostinger VM

Date: 2026-11-26
VM: srv1357760 (76.13.185.172), 2 vCPU, 7.8 GB RAM + 4 GB swap, 66 GB disk free

## Status (2026-11-26): running on the VM

What's running now:

- `docker-compose.vm.yml` runs backend (:8000), Celery worker, frontend
  (:3100), Redis and Neo4j Community. Everything uses host networking and
  binds 127.0.0.1. Host Postgres 17 is used as-is.
- Secrets are in `backend/.env.vm.local` and `.env.vm.local`, both
  git-ignored. JWT and encryption keys were freshly generated, the `smriti`
  role got a new password, and the old Cloud Run secrets aren't used.
- Host nginx serves `smriti.neetiq.in` from
  `/etc/nginx/sites-available/smriti.neetiq.in`. ufw allows 80/443.
- Neo4j was rebuilt from Postgres with `populate_neo4j.py`: 2,863 cases,
  332 citation edges, 5,162 acts, 1,628 judges. As a side effect, the script
  also updated `cases.cited_by_count` for 144 cases.
- Backup before any change: `/var/backups/smriti/smriti-20261126-1105.dump`.
- Providers: `VECTOR_PROVIDER=pgvector` (0 vectors so far),
  `RERANKER_PROVIDER=none` (new passthrough reranker), `STORAGE_PROVIDER=local`,
  `TTS_PROVIDER=mock`. Without a Gemini key, search runs keyword-only.

Still to do:

1. DNS: in Netlify DNS for neetiq.in, replace the `smriti` CNAME
   (`ghs.googlehosted.com`) with an A record pointing to `76.13.185.172`.
   Then run `certbot --nginx -d smriti.neetiq.in`. Login needs HTTPS
   because production sets secure cookies.
2. AI: create a Gemini API key in AI Studio, in a Google Cloud project
   **with no billing account attached**, so it's free tier only and can
   never charge. Put it in `GEMINI_API_KEY` in `backend/.env.vm.local` and
   restart backend and worker. The models are set to `gemini-2.5-flash`,
   `gemini-2.5-flash-lite` and `gemini-embedding-001` (1536-dim) to stay
   within free-tier quotas.
3. Embed cases into pgvector, slowly, within free-tier daily limits.

## Where things stand today

`https://smriti.neetiq.in` returns a Google 503. The domain is a CNAME to
`ghs.googlehosted.com`, which is a Cloud Run domain mapping, so the frontend
and backend went down with the GCP project (`smriti-489416`).

Each piece of the system and where it lives right now:

| Component | Where it runs | State | Source of truth? |
|---|---|---|---|
| Frontend (Next.js 16) | Cloud Run `smriti-frontend` | Down | Code in repo |
| Backend API (FastAPI) | Cloud Run `smriti-backend` | Down | Code in repo |
| Celery worker | Cloud Run `smriti-worker` | Down | Code in repo |
| Secrets (JWT, encryption key, API keys) | GCP Secret Manager | At risk | **Only copy** |
| PDFs / audio uploads | GCS `smriti-489416-documents` | At risk | `documents` and `audio_digests` tables are empty, so probably nothing important |
| Main database | **This VM**, Postgres 17, db `smriti` (778 MB) | Up | **Yes** |
| Vectors (153,755, 1536-dim) | Pinecone Pro trial | Probably expired | No, can be rebuilt from Postgres |
| Citation graph | Neo4j AuraDB Free | Probably paused or deleted | No, can be rebuilt from Postgres |
| Cache / rate limiting / Celery broker | Upstash Redis | Unknown | No |
| LLM + embeddings | Gemini via Vertex AI (trial credits) | Gone with the trial | n/a |
| Bulk ingestion (`turbo_ingest.py`) | Vertex Batch + GCS, several GCP trial accounts | Gone | n/a |
| Reranker | Cohere API | Unknown | n/a |
| TTS | Sarvam API, mock fallback | Unknown | n/a |

The good news: the data that matters is already on this VM. Postgres has
2,863 cases, 34,839 case sections, 9,016 statutes, 6,367 statute
interpretations and 4 users. `pgvector` 0.8.0 is installed and migration 017
already created `case_vectors` (HNSW index) and `citations`. Both are empty.
`cases.cases_cited` is filled in for 2,513 cases, which is exactly what
`scripts/populate_neo4j.py` builds the graph from.

The Supabase project called `smriti` (paused) is not what production used.
The Secret Manager script points `DATABASE_URL` at this VM. It can be ignored
or deleted.

## What can and can't be local

All the storage and serving pieces can come onto the VM: frontend, API,
worker, Postgres, vectors, graph, Redis, file storage, and the web server
with TLS.

The LLM cannot. Smriti's chat, research agents, drafting and ingestion
metadata extraction lean on Gemini Pro/Flash-class reasoning. A 2-vCPU box
with no GPU can't run a model anywhere near that quality at usable speed.
So "everything on this VM" really means everything except the model calls,
which go out over an API key. Embeddings and reranking are a closer call,
covered under the decisions below.

## Decisions to make before starting

1. **LLM provider.** The cheapest path with no code change is a Gemini API
   key from AI Studio on a billing account you control, with a monthly spend
   cap. `ingestion/COST_RULES.md` bans AI Studio, but only because Vertex
   trial credits were free at the time. That reason is gone now.
2. **Embeddings.** Pick one:
   - **(a) Recommended:** Gemini `gemini-embedding-2-preview` on the same
     key. The query-time model stays the same, so if Pinecone still answers
     we can export the 153k vectors as they are and only re-embed what's
     missing. A full re-embed is roughly 150k chunks, a few dollars.
   - (b) A local CPU model such as `bge-m3`. Free per call, but it needs a
     new provider class and a full re-embed (about a day of CPU on this
     box), and retrieval quality on Indian legal text would have to be
     re-checked.
3. **Graph store.** Recommended: **Neo4j Community in Docker on the VM.**
   The Postgres "drop-in" (`pg_graph_store.py`) is not actually a drop-in.
   Its `query()` runs whatever string it gets as SQL, and the app passes it
   44 raw Cypher queries from `graph/traversal.py`, `ingestion/pipeline.py`,
   `chat/rag.py`, the agent nodes and `routes/graph.py`. Switching
   `GRAPH_PROVIDER=postgresql` would break the graph page, citation
   expansion in chat, and the agents. Running Neo4j locally needs no code
   changes, and the graph is small (about 11k case nodes).
4. **Reranker.** Keep Cohere if the key still works. It's not GCP and the
   usage is small. Otherwise turn reranking off, or add a local cross-encoder
   later.
5. **DNS.** `smriti.neetiq.in` has to move from the Google CNAME to an A
   record for 76.13.185.172. You'll need to make that change wherever
   neetiq.in's DNS is managed.

## The plan

Each phase ends in a state we can check before moving on.

### Phase 0: Save what only exists on GCP (do this first, it's time-sensitive)

- Open the GCP console while it still lets you in and copy every secret out
  of Secret Manager: `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`,
  `ENCRYPTION_KEY`, `GEMINI_API_KEY(S)`, `PINECONE_*`, `NEO4J_*`,
  `COHERE_API_KEY`, `IK_API_TOKEN`, `TAVILY_API_KEY`, `SENTRY_DSN`,
  `REDIS_URL`. Losing `ENCRYPTION_KEY` makes encrypted fields unreadable.
  Losing the JWT keys only logs everyone out.
- List the GCS bucket and download anything in it.
- Try the Pinecone and AuraDB keys. If either is still alive, export it now
  (Pinecone: list + fetch by id into a local file; Neo4j: no export needed
  since it rebuilds from Postgres).

### Phase 1: Back up and lock down Postgres

- `pg_dump -Fc smriti` to `/var/backups/smriti/` and check the dump
  restores into a scratch database. This cluster is production data, so
  nothing else happens until there's a tested backup.
- Postgres listens on `0.0.0.0:5432`, and `pg_hba.conf` accepts `smriti`
  over SSL from any address. That was there for Cloud Run. Once Cloud Run
  is gone, restrict access to localhost plus the Docker bridge
  (172.17.0.0/16), and keep 5432 closed in the firewall.
- Add a nightly `pg_dump` with 7-day rotation.

### Phase 2: Code changes (small, one commit each)

- `app/core/config.py` production validator: only require Pinecone keys
  when `VECTOR_PROVIDER=pinecone` and only check the Neo4j password when
  `GRAPH_PROVIDER=neo4j`. Allow `storage_provider=local`. Allow
  `tts_provider=mock` (or make TTS optional) until Sarvam is decided.
  `database_url must not contain 'localhost'` blocks a local database, so
  either connect via the Docker host gateway or drop that check.
- `app/main.py` startup check: only run the Pinecone dimension check when
  the vector provider is Pinecone, and add an equivalent pgvector check.
- `app/api/routes/health.py`: same provider-aware treatment.
- Confirm `pgvector_store.upsert()` accepts the same vector dicts the
  ingestion pipeline produces (id, values, metadata). The interface says it
  does. Prove it with one case end-to-end.
- Leave Gemini on the API-key path (`GEMINI_USE_VERTEXAI=false`).

### Phase 3: Bring up the services on the VM

Use a new `docker-compose.vm.yml`, **not** the existing
`docker-compose.prod.yml`. That file starts its own Postgres container on
5432 with `shared_buffers=2GB`, which would collide with the host Postgres
that already holds the data and would double the memory.

| Service | How | Memory budget |
|---|---|---|
| Postgres 17 | Host install already running | ~2.5 GB (shared_buffers already 2 GB) |
| Neo4j 5 Community | Docker, heap 512 MB, page cache 256 MB, ports bound to 127.0.0.1 | ~1 GB |
| Redis 7 | Docker, `maxmemory 128mb`, bound to 127.0.0.1 | ~150 MB |
| Backend (uvicorn, 2 workers) | Docker, existing `Dockerfile` | ~1 GB |
| Celery worker (concurrency 1) | Docker, existing `Dockerfile.worker` | ~700 MB |
| Frontend (Next.js) | Docker, existing Dockerfile, built with `NEXT_PUBLIC_API_URL=/api/v1` | ~300 MB |
| Nginx + certbot | Host nginx (ports 80/443 are free) | small |

That's roughly 6 GB on top of what openclaw, hermes and the WhatsApp bridge
already use (about 2 GB). It fits, but it's tight, and the 4 GB swap is the
safety margin. If it gets squeezed, Postgres `shared_buffers` can drop to
1 GB without much cost at 778 MB of data. Avoid ports 3000 and 18789: the
WhatsApp bridge and openclaw already use them.

Run `alembic upgrade head`. The database is at revision 039, so check
whether that's already head.

### Phase 4: Rebuild vectors and graph locally

- **Graph:** run `scripts/populate_neo4j.py` against local Neo4j, then
  `build_citation_communities.py` and `compute_graph_analytics.py`. Compare
  node and edge counts with `INGESTION_STATE.md` (about 11.4k case nodes,
  10.1k CITES edges).
- **Vectors:** if the Pinecone export worked, bulk-load it into
  `case_vectors`. Otherwise re-embed from Postgres with
  `VECTOR_PROVIDER=pgvector` using `backfill_missing_vectors.py`, after a
  dry run on 10 cases. That run also picks up the 723 cases that never got
  vectors in Pinecone.
- Check: search for a known case title, a citation, and a topical query.
  Compare results with a few saved results (`search_result.json`).

### Phase 5: Go live

- Nginx server block for `smriti.neetiq.in`: `/api/` to backend (with SSE
  buffering off and a 300 s read timeout, as in `nginx/nginx.conf`), and
  everything else to the frontend. Get a certificate with certbot.
- Set `CORS_ORIGINS=https://smriti.neetiq.in`.
- Switch DNS. Then test login, search, a case page, the graph page, one
  chat, and one research agent run.
- Enable Docker `restart: unless-stopped` and confirm everything comes back
  after a reboot.

### Phase 6: Ingestion going forward

`turbo_ingest.py` and `batch_ingest_vertex.py` only work with Vertex + GCS
and the multi-account trial setup, so they're retired. For new judgments,
use the single-case pipeline (`ingest_s3.py` / `daily_ingest.py`) through the
Gemini API key, with a low concurrency and the spend cap as the brake. Bulk
backfills can use the Gemini Batch API on the same key (about half the
price). That's a later piece of work and not needed to go live.

## Risks

- **Secrets.** If Secret Manager is already locked, `ENCRYPTION_KEY` is
  gone. Damage is limited: `chat_messages` has 0 rows, and there are 22
  agent sessions and 2 shared memos. New JWT keys just mean everyone logs
  in again.
- **Memory pressure** on a 2-vCPU / 8 GB box running openclaw and hermes
  too. Watch it for the first week and cap container memory.
- **Shared Postgres.** The Smriti database sits in the same cluster that's
  treated as production. Back up first, and run migrations only after the
  dump has been restore-tested.
- **Model cost** is now real money on your own card. Set the cap before
  the first ingestion run.
