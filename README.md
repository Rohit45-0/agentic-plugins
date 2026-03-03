# catalyst-nexus-plugins

Standalone WhatsApp RAG Bot microservice for Catalyst Nexus.
Runs on **port 8001** independently from `catalyst-nexus-core` (port 8000).
Shares the same PostgreSQL database — no data duplication.

---

## Folder Structure

```
catalyst-nexus-plugins/
├── .env                          # Secrets: Azure, WhatsApp, DB URL, owner phone
├── requirements.txt              # Python dependencies
├── main.py                       # FastAPI entry point (port 8001)
└── app/
    ├── core/config.py            # Settings from .env
    ├── db/
    │   ├── base.py               # DB engine → shared PostgreSQL
    │   └── models.py             # User + KnowledgeChunk (mirrors core tables)
    ├── services/
    │   ├── rag_service.py        # Embed text, semantic search, ingest chunks
    │   └── whatsapp_service.py   # Send messages, download media, mark read
    └── api/
        └── whatsapp.py           # THE BRAIN — webhook handler & routing logic
```

---

## How to Run

```bash
cd "d:\Catalyst Nexus\catalyst-nexus-plugins"
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Then expose it publicly for Meta webhook:
```bash
lt --port 8001
```

Update Meta Dashboard → WhatsApp → Configuration → Webhook:
- **Callback URL:** `https://<your-lt-url>/api/v1/whatsapp/webhook`
- **Verify Token:** `catalyst_nexus_webhook_secret`

---

## The Two Message Flows

### Flow A — Owner Texts the Bot
> Triggered when `OWNER_PHONE_NUMBER` in `.env` matches the sender.

| Owner sends | Bot does |
|-------------|----------|
| Any text | Ingests it as knowledge into pgvector |
| `.txt` / `.csv` file | Downloads, extracts text, ingests |
| Anything else | Explains what it accepts |

### Flow B — Customer Texts the Bot
> Triggered for every other phone number.

1. Extract the customer's question from the message
2. Search `knowledge_chunks` table using cosine similarity (pgvector)
3. Feed question + top 5 matching chunks to `gpt-4o-mini`
4. Send the AI reply back on WhatsApp

---

## Key Environment Variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Same Supabase PostgreSQL as core |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI for embeddings + chat |
| `AZURE_DEPLOYMENT_NAME` | Set to `gpt-4o-mini` (cost-efficient) |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID |
| `WHATSAPP_ACCESS_TOKEN` | Meta API bearer token |
| `WHATSAPP_VERIFY_TOKEN` | `catalyst_nexus_webhook_secret` |
| `OWNER_PHONE_NUMBER` | e.g. `919325341766` — gets admin mode |

---

## What's Done ✅

- [x] Meta webhook verification (GET)
- [x] Incoming message listener (POST) — async background processing
- [x] Owner flow: text ingestion + document download
- [x] Customer flow: RAG search + GPT-4o-mini reply
- [x] WhatsApp service: send text, download media, mark read
- [x] RAG service: embed, search, ingest
- [x] Shared DB connection (same tables as core)

## What's Next 🔨

- [ ] Install deps and do first live end-to-end test
- [ ] PDF support (`pdfplumber`)
- [ ] Voice note transcription (Whisper API)
- [ ] Multi-tenant support (map WhatsApp number → merchant `user_id`)
- [ ] Google Calendar booking tools (Phase 2)
- [ ] Frontend dashboard page in `nural-knights123`
- [ ] Broadcast feature (owner sends promo to all customers)
- [ ] Deploy to production (Docker + Render/GCP)

---

## How It Connects to catalyst-nexus-core

- **Same DB:** Both services read/write `users` and `knowledge_chunks` tables.
- **Same Frontend:** `nural-knights123` calls `localhost:8000` for campaigns and `localhost:8001` for WhatsApp bot management.
- **Future Merge:** To merge back into core, copy `app/api/whatsapp.py` into `catalyst-nexus-core/backend/app/api/v1/` and register it in `main.py`.
