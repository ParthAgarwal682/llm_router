# LLM Router Arbitration Platform

> **Intelligent LLM routing with automated arbitration and real-time dollar savings tracking vs. GPT-4o.**

A production-grade, multi-user ChatGPT/Claude-style web application and API service. Prompts are classified and routed to the cheapest capable model via OpenRouter, verified in the background against strong models, and arbitrated by a 3-critic LangGraph panel when disagreements arise—all while showing each user exactly how much money they save compared to always using GPT-4o.

---

## Key Features

- **ChatGPT/Claude-Style Web Workspace (`/web`)**: Modern Next.js (App Router, Tailwind CSS, Lucide icons) interface with sidebar chat management, auto-expanding composer, and real-time SSE token streaming.
- **Headline Savings Transparency**: 
  - Every response displays a **Quality Badge** with tier level (`Simple`, `Moderate`, `Complex`), model used, and exact dollar savings vs GPT-4o.
  - Dedicated **Usage & Savings Analytics** page (`/usage`) detailing lifetime dollar ROI, average savings %, cost comparison charts, and daily financial audit logs.
- **Multi-Tenant User Authentication & Isolation**:
  - Secure registration and login (`/v1/auth/register`, `/v1/auth/login`).
  - Short-lived JWT access tokens + rotating httpOnly refresh cookies (`/v1/auth/refresh`, `/v1/auth/logout`).
  - Strict user-level data isolation across conversations, prompt messages, and request cost logs.
  - Per-user sliding-window rate limiting.
- **Smart 3-Tier Dynamic Routing**:
  - **Simple** (`llama_8b`): Greetings, basic definitions, trivial lookups (~98% cheaper than GPT-4o).
  - **Moderate** (`llama_70b`): Structured data tasks, moderate logic, code refactoring.
  - **Complex** (`claude_sonnet` / `gpt4o`): Deep architectural questions, complex multi-step reasoning.
- **Verification & Arbitration Engine**:
  - **Single-Judge Verifier**: Asynchronously compares cheap model output against strong model reference.
  - **3-Critic LangGraph Arbitration**: Escalates when disagreement occurs, running 3 independent critics (factual accuracy, reasoning soundness, instruction adherence) and a final adjudicator.
  - Live status updates delivered to the UI via Server-Sent Events (`/v1/requests/{id}/events`).

---

## Architecture Overview

```text
User Prompt (Next.js Web / API)
        │
        ▼
Complexity Classifier (Feature Extractor + Heuristics)
        │
   ┌────┴───────────────────────────┐
   ▼                                ▼                                ▼
Simple Tier                   Moderate Tier                   Complex Tier
(e.g., Llama 3.1 8B)          (e.g., Llama 3.3 70B)          (e.g., Claude 3.5 Sonnet / GPT-4o)
   │                                │                                │
   └────────────────────────────────┼────────────────────────────────┘
                                    ▼
                         SSE Token Stream to User
                                    │
                         (Background Asynchronous)
                                    ▼
                         Single-Judge Verifier
                                    │
                      ┌─────────────┴─────────────┐
                   AGREE                       DISAGREE
                      │                           │
                      ▼                           ▼
               Mark Verified             3-Critic LangGraph Jury
                                         (Fact, Logic, Instruction)
                                                  │
                                                  ▼
                                             Adjudicator
                                                  │
                                                  ▼
                                       Final Verdict & Cost Log
```

---

## Quickstart (Local Development)

### Prerequisites
- Python 3.10+ (with virtualenv)
- Node.js 18+ and npm
- OpenRouter API key ([https://openrouter.ai/keys](https://openrouter.ai/keys))

### 1. Backend Setup

```bash
# Clone and enter repo
cd llm-router-arbitration

# Create virtual environment & activate
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env and ensure:
# OPENROUTER_API_KEY=your_key_here
# JWT_SECRET=your_random_secret_key_here

# Train routing classifier
python -m src.routing.train_classifier

# Start FastAPI backend (port 8000)
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup (Next.js)

In a new terminal:

```bash
cd web

# Install dependencies
npm install

# Start Next.js development server (port 3000)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser:
- Register an account at `/register`
- Start chatting in the `/chat` workspace
- View live savings metrics at `/usage`

### 3. Optional Admin Dashboard (Streamlit)

In a separate terminal:

```bash
source .venv/bin/activate
streamlit run src/dashboard/app.py
```
Open [http://localhost:8501](http://localhost:8501) for system-wide cost analytics and verdict explorations.

---

## Running with Docker Compose

To spin up all services (`api`, `web`, and `dashboard`) with a single command:

```bash
docker compose up --build
```

- **Next.js Web UI**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend & Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Streamlit Admin Dashboard**: [http://localhost:8501](http://localhost:8501)

---

## API Endpoints Reference

### Authentication (`/v1/auth/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/auth/register` | None | Register with `{email, password}`. Returns access token + sets refresh cookie. |
| `POST` | `/v1/auth/login` | None | Login with `{email, password}`. Returns access token + sets refresh cookie. |
| `POST` | `/v1/auth/refresh` | Cookie | Rotates refresh token and returns new `{access_token}`. |
| `POST` | `/v1/auth/logout` | Required | Revokes refresh token and clears cookie. |
| `GET` | `/v1/auth/me` | Required | Current user details, daily limit, and request counter. |

### Chat & Streaming (`/v1/chat/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/v1/chat/stream` | Required | SSE stream delivering `meta` → `token`* → `done` events with live savings math. |

### Conversations (`/v1/conversations/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/conversations` | Required | List user's conversations (paginated). |
| `POST` | `/v1/conversations` | Required | Create a new conversation. |
| `PATCH` | `/v1/conversations/{id}` | Required | Rename conversation title. |
| `DELETE` | `/v1/conversations/{id}` | Required | Delete conversation and associated messages. |
| `GET` | `/v1/conversations/{id}/messages` | Required | Retrieve all messages for a specific conversation. |

### Requests & Verification Status (`/v1/requests/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/requests/{id}` | Required | Fetch request details and finalized costs (scoped to user). |
| `GET` | `/v1/requests/{id}/events` | Required | SSE stream emitting status transitions (`verifying` → `arbitrating` → `final`). |

### Analytics & Stats (`/v1/me/`)
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/v1/me/stats?range=7d\|30d\|all` | Required | User savings breakdown, model distribution, and daily financial audit series. |

---

## Cost & Savings Calculation Logic

For every prompt processed:
1. **Answer Cost (`answer_cost`)**: Exact token cost of the routed model calculated from input/output tokens using OpenRouter pricing registry.
2. **Baseline Cost (`baseline_cost_usd`)**: What the same prompt and response tokens would have cost on **GPT-4o** ($2.50 / $10.00 per million tokens).
3. **Verification Cost (`verification_cost`)**: Any tokens consumed by background judges and multi-critic arbitration.
4. **Net Dollar Saved (`net_saved`)**:
   $$\text{Net Saved} = \text{Baseline Cost} - (\text{Answer Cost} + \text{Verification Cost})$$
   *Net savings can be negative in rare cases if an answer is heavily escalated, and is never falsely clamped.*

---

## Testing

Run the full pytest suite (covering auth, user data isolation, savings math pure functions, and rate limiting):

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

All 28 unit and integration tests are verified passing:
- `tests/test_auth.py`: Registration, login, validation, refresh token rotation, logout.
- `tests/test_isolation.py`: Cross-user data isolation on conversations, messages, and request logs.
- `tests/test_costs.py`: Pure savings calculations, edge cases, breakeven, and negative savings handling.

---

## Repository Structure

```text
llm-router-arbitration/
├── docker-compose.yml          # Multi-container orchestration (api, web, dashboard)
├── Dockerfile                  # Production API container image
├── requirements.txt            # Python dependencies (FastAPI, LangGraph, Jose, etc.)
├── config/
│   └── routing.yaml            # Tier mappings and model definitions
├── web/                        # Next.js multi-user web application
│   ├── app/                    # App Router (login, register, chat, usage)
│   ├── components/             # UI components (Sidebar, MessageBubble, Composer, QualityBadge)
│   ├── hooks/                  # useAuth, useStream hooks
│   └── lib/                    # api client and formatters
├── src/
│   ├── api/                    # FastAPI routes, auth, deps, SSE streams
│   ├── models/                 # Model registry & pricing definitions
│   ├── routing/                # ML complexity classifier & fallback router
│   ├── verification/           # Single-judge verification pipeline
│   ├── arbitration/            # LangGraph 3-critic jury & adjudicator
│   ├── storage/                # SQLite storage & schema migrations
│   └── dashboard/              # Streamlit admin analytics app
├── scripts/                    # Batch benchmarks & smoke tests
└── tests/                      # Automated pytest test suite
```

---

## License

MIT
