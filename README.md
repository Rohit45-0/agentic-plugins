# catalyst-nexus-plugins

Standalone WhatsApp RAG Bot microservice for Catalyst Nexus.
Runs on **port 8001** independently from `catalyst-nexus-core` (port 8000).
Shares the same PostgreSQL database with core.

---

## Folder Structure

```text
catalyst-nexus-plugins/
|-- .env                          # Secrets: OpenAI, WhatsApp, DB URL, internal webhook secret
|-- requirements.txt              # Python dependencies
|-- main.py                       # FastAPI entry point (port 8001)
`-- app/
    |-- core/config.py            # Settings from .env
    |-- db/
    |   |-- base.py               # DB engine -> shared PostgreSQL
    |   `-- models.py             # User + KnowledgeChunk (mirrors core tables)
    |-- services/
    |   |-- rag_service.py        # Embed text, semantic search, ingest chunks
    |   `-- whatsapp_service.py   # Send messages, download media, mark read
    `-- api/
        `-- whatsapp.py           # Webhook handler and routing logic
```

---

## How to Run

```bash
cd "d:\Catalyst Nexus\catalyst-nexus-plugins"
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Run workers (required when `WEBHOOK_USE_CELERY=true`):

```bash
sh scripts/railway-start-worker.sh webhook_ingest
sh scripts/railway-start-worker.sh llm_reply
sh scripts/railway-start-worker.sh media
```

For Railway, each queue must be a long-lived service, not a one-off job:

```text
web                   -> sh scripts/railway-start-web.sh
worker-webhook-ingest -> sh scripts/railway-start-worker.sh webhook_ingest
worker-llm-reply      -> sh scripts/railway-start-worker.sh llm_reply
worker-media          -> sh scripts/railway-start-worker.sh media
```

If `worker-llm-reply` shows `Completed` instead of `Online`, customer text messages will stop because text events are routed to the `llm_reply` queue.

Expose it publicly for Meta webhook:

```bash
lt --port 8001
```

Update Meta Dashboard -> WhatsApp -> Configuration -> Webhook:
- **Callback URL:** `https://<your-lt-url>/api/v1/whatsapp/webhook`
- **Verify Token:** set the same value as `WHATSAPP_VERIFY_TOKEN`

---

## The Two Message Flows

### Flow A - Owner Texts the Bot
Triggered when `OWNER_PHONE_NUMBER` in `.env` matches the sender.

| Owner sends | Bot does |
|-------------|----------|
| Any text | Ingests it as knowledge into pgvector |
| `.txt` / `.csv` file | Downloads, extracts text, ingests |
| Anything else | Explains what it accepts |

### Flow B - Customer Texts the Bot
Triggered for every other phone number.

1. Extract the customer question from the message.
2. Search `knowledge_chunks` using cosine similarity (pgvector).
3. Feed question + top 5 matching chunks to `gpt-4o-mini`.
4. Send AI reply back on WhatsApp.

---

## Key Environment Variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Same Supabase PostgreSQL as core |
| `OPENAI_API_KEY` | OpenAI key for embeddings + chat completions |
| `SECRET_KEY` | JWT signing key (must match core if sharing auth token) |
| `FERNET_KEY` | Encryption key for stored Google OAuth tokens |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | Meta API bearer token |
| `WHATSAPP_VERIFY_TOKEN` | Meta webhook verification token |
| `INTERNAL_WEBHOOK_SECRET` | Required header secret for `/api/v1/whatsapp/system-alert` |
| `REDIS_URL` | Redis/Celery broker + distributed rate limiting backend |
| `OWNER_PHONE_NUMBER` | Owner/admin number for training mode |

---

## What's Done

- [x] Meta webhook verification (GET)
- [x] Incoming message listener (POST) with queued processing (Celery/Redis)
- [x] Owner flow: text ingestion + document download
- [x] Customer flow: RAG search + GPT-4o-mini reply
- [x] WhatsApp service: send text, download media, mark read
- [x] RAG service: embed, search, ingest
- [x] Shared DB connection (same tables as core)

## What's Next

- [ ] Install deps and do first live end-to-end test
- [ ] PDF support (`pdfplumber`)
- [ ] Voice note transcription (Whisper API)
- [ ] Multi-tenant support (map WhatsApp number -> merchant `user_id`)
- [ ] Broadcast feature (owner sends promo to all customers)
- [ ] Deploy to production (Docker + Render/GCP)

---

## How It Connects to catalyst-nexus-core

- **Same DB:** Both services read/write `users` and `knowledge_chunks` tables.
- **Same frontend auth model:** plugin verifies JWT from the same auth source.
- **System alert security:** core must send `X-Internal-Secret` header.
