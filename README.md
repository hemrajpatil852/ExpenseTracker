# Rupee Ledger: expense classification and reporting

Upload a bank-statement CSV, get every transaction auto-categorised, and explore spending by category and time period.

**Stack:** React 18 + Vite + Tailwind CSS v4 + Axios + Recharts | FastAPI + SQLAlchemy | SQLite (dev) / PostgreSQL (prod) | Docker

> **Styling rule honoured:** `src/index.css` contains only `@import "tailwindcss";` (Tailwind's required entry line). All styling is standard Tailwind utility classes in JSX. No custom CSS.
> **API rule honoured:** every endpoint is `POST`, called through Axios. `GET` returns 405 (there is a test for it).

## 1. Run locally

```bash
# Backend (Python 3.11+)
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # optional; defaults work for dev
uvicorn app.main:app --reload --port 8000              # API docs: http://localhost:8000/api/docs

# Frontend (Node 18+), second terminal
cd frontend
npm install
npm run dev                                            # http://localhost:5173 (proxies /api to :8000)
```
Sign up, then upload `sample_statement.csv` from the repo root.

With Docker (Postgres + API): `docker compose up --build`, then run the frontend as above.

## 2. Tests
```bash
cd backend && pytest -v
```
Covers: POST-only enforcement, auth flow, token revocation, expired tokens, login rate limit, CSV parsing (bank preamble, Indian number format, delimiters, encodings, bad rows, corrupt/binary/empty files), categorisation priority, dedupe (re-upload, overlap, identical in-file rows), oversize rejection, 5,000-row upload, tenant isolation, dashboard maths, CSV-injection guard, PDF export, cascade delete.

## 3. Deploy (free)
1. **API on Render:** push to GitHub, then *New > Blueprint* and pick the repo (uses `render.yaml`: Docker service + free Postgres). Set `CORS_ORIGINS` to your Vercel URL.
2. **Frontend on Vercel:** import the repo, root directory `frontend`, env var `VITE_API_URL=https://<your-render-service>.onrender.com/api`. `vercel.json` handles SPA routing.
3. Free Render instances sleep when idle, so the first request after a pause takes about 30s.

## 4. Architecture
```
 Browser (React SPA, Vercel)
   |  Axios, POST + JSON / multipart, Bearer JWT
   |  interceptor: 401 -> POST /auth/refresh -> replay request
   v
 FastAPI (Render, Docker, uvicorn)
   routers: auth | uploads | transactions+categories | dashboard | export
   services: csv_parser -> ingest (hash, dedupe, categorise, bulk insert)
   security: bcrypt, JWT (access 30 min / refresh 7 d), rate limit, CORS, headers
   |  SQLAlchemy ORM
   v
 PostgreSQL (SQLite for local dev)
```
**Upload data flow:** file -> size/extension checks -> decode (UTF-8/CP1252) -> delimiter sniff -> header-row detection -> per-row parse (bad rows collected, not fatal) -> hash each row -> drop hashes already stored for this user -> categorise (user rules, then system rules, then fallback) -> one bulk insert -> upload summary returned.

**Why these choices**
- *FastAPI:* typed request validation, async file reads, automatic OpenAPI docs.
- *SQLAlchemy:* one codebase for SQLite (zero-setup dev) and PostgreSQL (prod).
- *POST everywhere:* filters, tokens and dates never land in URLs, server logs or browser history. Trade-off: no HTTP caching of reads (acceptable for private financial data; `Cache-Control: no-store` is set anyway).
- *Rule-based categoriser:* deterministic, explainable, editable by users. An ML/LLM classifier could slot in behind `Categorizer.categorize` for unmatched rows.
- *Aggregation in SQL:* dashboard cost depends on the number of categories and days, not on transaction count.

**Security:** bcrypt (cost 12); password policy; short-lived access tokens plus refresh tokens; logout bumps `token_version` which revokes every token; refresh tokens cannot be used as access tokens; every query is scoped by `user_id`; login brute-force limiter; strict CORS (POST only); `nosniff`, `X-Frame-Options`, `no-store`; upload size and row caps; CSV-formula-injection neutralised on export; ORM parameter binding and escaped `LIKE` search; generic 500 messages. Set a long random `SECRET_KEY` in production.

## 5. Database schema
| Table | Columns |
|---|---|
| `users` | id, email (unique), name, password_hash, token_version, created_at |
| `categories` | id, user_id (NULL = system), name, keywords (comma list); unique(user_id, name) |
| `uploads` | id, user_id, filename, status (completed/failed), total_rows, inserted, duplicates, skipped, error_report (JSON), message, created_at |
| `transactions` | id, user_id, upload_id (cascade), category_id, txn_date, description, amount (positive Numeric 14,2), txn_type (debit/credit), balance, dedupe_hash, created_at; **unique(user_id, dedupe_hash)**, index(user_id, txn_date) |

## 6. API (all `POST`, JSON unless noted; all but signup/login/refresh/health need `Authorization: Bearer <access>`)
| Endpoint | Body | Returns |
|---|---|---|
| `/api/auth/signup` | name, email, password | tokens + user |
| `/api/auth/login` | email, password | tokens + user |
| `/api/auth/refresh` | refresh_token | new tokens |
| `/api/auth/logout` | none | ok (revokes tokens) |
| `/api/auth/me` | none | user |
| `/api/uploads/create` | multipart `file` (.csv) | inserted, duplicates, skipped, errors[] |
| `/api/uploads/list` | none | upload history |
| `/api/uploads/delete` | id | ok (removes its transactions) |
| `/api/transactions/list` | page, page_size, search, category_id, txn_type, start_date, end_date | items, total |
| `/api/transactions/update-category` | transaction_id, category_id | updated transaction |
| `/api/categories/list` / `create` / `delete` | none / name, keywords[], reapply / id | categories |
| `/api/dashboard/summary` | start_date, end_date, group_by (day/week/month) | totals, categories[], timeline[] |
| `/api/export/csv` and `/api/export/pdf` | same filters | file download |
| `/api/health` | none | status |

## 7. Edge cases
| Case | Handling |
|---|---|
| Malformed / corrupt CSV | Binary, empty, header-less or all-invalid files return 422 with a plain-language reason and are logged as *failed* uploads. Individual bad rows are skipped and listed (row number + reason) while good rows import. |
| Bank preamble, odd formats | Header row found within first 40 lines; aliases for HDFC/ICICI/SBI-style columns; `1,250.50`, `Rs.`, `₹`, `(500)`, `Dr/Cr` suffixes; several date formats; `,` `;` tab `|` delimiters; UTF-8/CP1252. |
| Duplicates / overlap | Row hash + occurrence counter + DB unique constraint. Re-uploads and overlapping date ranges add only new rows, while two genuinely identical same-day payments in one file are both kept. |
| Session expires mid-upload | Axios interceptor refreshes the token once and replays the multipart request. If the refresh token is also dead, the user is sent to login with a clear message. |
| Large files | 10 MB and 50,000-row caps, bounded read, chunked duplicate lookups, single bulk insert, streamed CSV export, PDF capped at 1,000 rows. |
| Concurrent identical uploads | Unique constraint catches the race and returns 409. |

## 8. Self-assessment
**Key choices and trade-offs.** I picked a rule-based categoriser over ML because it is predictable, needs no training data and users can correct it. Hash-based dedupe is fast and DB-enforced but cannot recognise the same transaction if a bank edits its narration between exports. JWTs are kept in `localStorage`, which keeps the deployment simple across two domains but is exposed to XSS; httpOnly cookies behind one domain would be stronger. Using one parser with header aliases covers most Indian banks without per-bank code, at the cost of not understanding unusual layouts.

**What worked well.** Row-level error reporting, so one bad line never blocks a statement; per-user rules that beat system rules; manual recategorisation; the single-flight token refresh; test coverage of the risky paths.

**What to improve.** Alembic migrations; Redis-backed rate limiting; httpOnly-cookie sessions; background jobs for very large files; PDF-statement parsing; learning from user corrections ("always put this merchant in X"); budgets and alerts; frontend tests (Vitest + Testing Library); encryption of descriptions at rest.

**Difficulties.** Bank CSVs are inconsistent, so I made the parser a pipeline of small tolerant steps rather than a strict schema. Dedupe was the subtle one: pure hashing would wrongly merge identical legitimate payments, which the occurrence counter solves. Replaying a multipart upload after a token refresh needed a shared single refresh promise to avoid refresh storms. SQLite does not enforce foreign-key cascades by default, so the dev engine turns the pragma on to match PostgreSQL.
