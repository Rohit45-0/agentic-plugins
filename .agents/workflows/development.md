---
description: How to safely develop, test, and deploy changes to the WhatsApp bot
---

# Development Workflow for Catalyst Nexus Plugins

## Golden Rule
**NEVER push directly to `main`. All work happens on feature branches.**
`main` = production. If it's on `main`, it's live on Railway within 2 minutes.

---

## 1. Before Starting Any Feature or Fix

// turbo
```bash
cd d:\Catalyst Nexus\catalyst-nexus-plugins
git checkout main
git pull origin main
```

Then create a branch:
```bash
git checkout -b <branch-type>/<short-name>
```

**Branch naming:**
- `fix/calendar-cancel-bug`
- `feat/google-docs-rag`
- `refactor/cleanup-whatsapp-handler`

---

## 2. While Developing

### Run the local server to test changes:
```bash
cd d:\Catalyst Nexus\catalyst-nexus-plugins
uvicorn main:app --reload --port 8001
```

### Run quick smoke tests before committing:
// turbo
```bash
cd d:\Catalyst Nexus\catalyst-nexus-plugins
python -c "from main import app; print('App loads OK')"
```

### Commit often with clear messages:
```bash
git add -A
git commit -m "fix: <what you fixed and why>"
```

**Commit message prefixes:**
- `fix:` — bug fix
- `feat:` — new feature
- `refactor:` — code cleanup (no behavior change)
- `chore:` — config, deps, CI changes

---

## 3. Before Merging to Main (Pre-Deploy Checklist)

Run ALL of these checks:

### 3a. App loads without import errors:
// turbo
```bash
python -c "from main import app; print('OK: App loads')"
```

### 3b. Database connection works:
// turbo
```bash
python -c "
import asyncio
from sqlalchemy import text
from app.db.base import AsyncSessionLocal
async def test():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text('SELECT 1'))
        print('OK: DB connected')
asyncio.run(test())
"
```

### 3c. Webhook handler doesn't crash:
// turbo
```bash
python -c "
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from app.api.whatsapp import _process_payload
async def test():
    payload = {'entry': [{'changes': [{'value': {'metadata': {'phone_number_id': '1025937603933608'}, 'messages': [{'from': '919325341766', 'id': 'test-smoke', 'type': 'text', 'text': {'body': 'test'}}]}}]}]}
    await _process_payload(payload)
    print('OK: Webhook processed')
asyncio.run(test())
"
```

### 3d. No emoji in logger calls (causes UnicodeEncodeError):
// turbo
```bash
python -c "
import re, glob
files = glob.glob('app/**/*.py', recursive=True)
issues = []
for f in files:
    for i, line in enumerate(open(f, encoding='utf-8'), 1):
        if 'logger.' in line and any(ord(c) > 127 for c in line):
            issues.append(f'{f}:{i}')
if issues:
    print('FAIL: Emoji found in logger calls:')
    for x in issues: print(f'  {x}')
else:
    print('OK: No emoji in loggers')
"
```

---

## 4. Merge to Main (Deploy)

```bash
git checkout main
git pull origin main
git merge <branch-name> --no-ff -m "merge: <what this adds>"
git push origin main
```

The `--no-ff` flag preserves the branch history so you can always see what was merged.

After pushing, Railway auto-deploys. Wait ~2 minutes, then verify:

// turbo
```bash
python -c "import urllib.request; r = urllib.request.urlopen('https://web-production-ba9e.up.railway.app/health', timeout=10); print('Railway:', r.read().decode())"
```

---

## 5. If Production Breaks (Emergency Rollback)

// turbo
```bash
cd d:\Catalyst Nexus\catalyst-nexus-plugins
git log --oneline -10
```

Then revert to the last known good commit:
```bash
git revert HEAD
git push origin main
```

Or hard reset (nuclear option):
```bash
git reset --hard <good-commit-hash>
git push origin main --force
```

---

## 6. Key Files — Handle With Care

These files crash the ENTIRE app if broken:

| File | Risk | What breaks |
|------|------|-------------|
| `app/db/base.py` | 🔴 CRITICAL | ALL database operations |
| `app/api/whatsapp.py` | 🔴 CRITICAL | ALL message processing |
| `app/core/config.py` | 🔴 CRITICAL | App won't even start |
| `main.py` | 🔴 CRITICAL | App won't start |
| `requirements.txt` | 🟡 HIGH | Dependency mismatches = silent crashes |
| `app/services/rag_service.py` | 🟡 HIGH | Customer replies break |
| `app/services/slot_engine.py` | 🟡 HIGH | Booking/cancel breaks |

---

## 7. Dependency Rules

- **Pin minimum versions** in `requirements.txt` using `>=` (e.g., `sqlalchemy>=2.0.34`)
- **Never run** `pip install -r requirements.txt` on your dev machine carelessly — it can downgrade working packages
- If you need to test with exact production versions, use a virtual environment:
  ```bash
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```

---

## 8. Environment Notes

- **Production DB:** Supabase PostgreSQL via PgBouncer (port 6543, transaction mode)
  - MUST have `statement_cache_size=0` and `prepared_statement_cache_size=0`
- **Production hosting:** Railway (auto-deploys from `main` branch)
- **Redis:** Upstash (requires `rediss://` with SSL)
- **WhatsApp API:** Meta Cloud API (test mode — only allowed phone numbers receive replies)
