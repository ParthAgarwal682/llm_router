# LLM Router & Arbitration Platform — Comprehensive System Architecture & Deep Dive

> **The Definitive Guide**: How this system works, how every subsystem communicates, how data is persisted, all engineering changes made, and a complete mastery roadmap.

---

## 1. Executive Summary & Purpose

The **LLM Router & Arbitration Platform** is an enterprise-grade AI gateway designed to solve the **"Cost vs. Intelligence Paradox"** in Large Language Model applications.

### The Problem
Organizations and users default to proprietary frontier models (e.g., OpenAI's **GPT-4o** at **$2.50 / $10.00 per million tokens**) for every prompt. In reality, **over 70% of prompts** are simple queries, formatting tasks, or basic transformations that do not require frontier reasoning. Sending trivial prompts to frontier models burns 90%+ of an organization's AI budget unnecessarily. Conversely, routing everything to cheap models introduces hallucinations, factual drift, and reasoning failures on complex prompts.

### The Solution
This platform implements an **Intelligent 3-Tier Router with Background Verification and LangGraph Multi-Critic Arbitration**:
1. **Dynamic ML Classification**: Every incoming user prompt is analyzed in under 2ms using a lightweight feature extraction pipeline and trained classifier to assign it to the cheapest capable tier (`Simple`, `Moderate`, or `Complex`).
2. **Instant Streaming to User**: The selected model streams tokens to the user immediately, eliminating routing latency.
3. **Background Single-Judge Verification**: In the background, cheap responses are spot-checked against a strong reference model.
4. **LangGraph 3-Critic Arbitration**: If the background judge flags a disagreement, the response is escalated to a 3-agent jury (Accuracy, Logic, and Completeness critics) and an Adjudicator to issue a binding quality verdict.
5. **Real-time Dollar Savings Ledger**: Every token is accounted for. The platform calculates exact token costs, baseline GPT-4o costs, verification overhead, and net dollar savings ($ and %) in real time.

---

## 2. End-to-End System Architecture

```
                                 ┌────────────────────────┐
                                 │      User Browser      │
                                 │  (Next.js Web / /chat) │
                                 └───────────┬────────────┘
                                             │ HTTP POST /v1/chat/stream
                                             ▼
                                 ┌────────────────────────┐
                                 │     FastAPI Server     │
                                 │ (Auth, JWT, Rate-Limit)│
                                 └───────────┬────────────┘
                                             │
                        ┌────────────────────┴────────────────────┐
                        ▼                                         ▼
            Feature Extractor & ML Classifier             Database Connection
          (src/routing/features.py, classifier.py)       (Creates Request in DB)
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
  Simple Tier     Moderate Tier    Complex Tier
 (Llama 3.1 8B)   (GPT-4o Mini)   (Llama 3.3 70B)
 (~98% cheaper)   (~90% cheaper)   (~95% cheaper)
       │                │                │
       └────────────────┼────────────────┘
                        ▼
           OpenRouter API Gateway
                        │
                        ▼
         Server-Sent Events (SSE) Stream
        (Instant token delivery to user UI)
                        │
                        ▼ (Background Asynchronous Task)
         Single-Judge Quality Verifier
         (src/verification/single_judge.py)
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
           [AGREE]            [DISAGREE]
              │                   │
              ▼                   ▼
       Mark Verified in DB   Escalate to LangGraph Jury
                             (src/arbitration/graph.py)
                                  │
                   ┌──────────────┼──────────────┐
                   ▼              ▼              ▼
               Critic 1:      Critic 2:      Critic 3:
               Accuracy         Logic       Completeness
             (GPT-4o Mini) (Claude Haiku)  (Llama 70B)
                   │              │              │
                   └──────────────┼──────────────┘
                                  ▼
                        Disagreement Detector
                                  │
                                  ▼
                         Adjudicator Node
                           (Final Verdict)
                                  │
                                  ▼
                     Audit DB Update & Final Math
                   (Answer + Verification Costs Logged)
                                  │
                                  ▼
                     SSE Event Push to UI
                     (/v1/requests/{id}/events)
```

---

## 3. Subsystem Deep Dive

### 3.1 Smart 3-Tier Dynamic Routing & Machine Learning Classifier

The classifier determines prompt complexity **locally on CPU in <2ms** without making costly API calls before routing.

- **Feature Extractor** ([`src/routing/features.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/routing/features.py)):
  Extracts 12 numerical features from the raw prompt text:
  1. `word_count`: Total whitespace-delimited tokens.
  2. `char_count`: Total character length.
  3. `approx_token_count`: Estimated token density (`char_count // 4`).
  4. `question_mark_count`: Direct interrogative markers.
  5. `sentence_count`: Sentence boundary markers (`.`, `!`, `?`).
  6. `avg_word_length`: Indicator of lexical sophistication.
  7. `analysis_word_count`: Matches against high-reasoning words (`analyze`, `compare`, `contrast`, `evaluate`, `tradeoff`, `critique`, `synthesize`, `steelman`).
  8. `constraint_word_count`: Matches against operational constraints (`must`, `should`, `exactly`, `json`, `format`, `threshold`, `criteria`, `limit`).
  9. `code_word_count`: Matches against software engineering terms (`def`, `function`, `api`, `refactor`, `algorithm`, `database`, `redis`, `postgres`).
  10. `has_numbered_steps`: Binary flag for multi-part requirements (`1.`, `2.`, `first`, `second`).
  11. `comma_count`: Syntactic clause complexity.
  12. `semicolon_count`: Compound sentence structure indicator.

- **Model Training** ([`src/routing/train_classifier.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/routing/train_classifier.py)):
  - Reads ground-truth prompt labels from [`data/labeled_prompts.csv`](file:///Users/parthagarwal/Projects/llm-router-arbitration/data/labeled_prompts.csv).
  - Uses a scikit-learn `Pipeline([('scaler', StandardScaler()), ('clf', LogisticRegression())])`.
  - Serializes the trained pipeline into [`data/complexity_classifier.joblib`](file:///Users/parthagarwal/Projects/llm-router-arbitration/data/complexity_classifier.joblib).

- **Tier Mapping** ([`config/routing.yaml`](file:///Users/parthagarwal/Projects/llm-router-arbitration/config/routing.yaml)):
  - **Simple Tier**: Mapped to `llama_8b` (`meta-llama/llama-3.1-8b-instruct`). Cost: **$0.00005 / $0.00008 per 1K tokens**.
  - **Moderate Tier**: Mapped to `gpt4o_mini` (`openai/gpt-4o-mini`). Cost: **$0.00015 / $0.0006 per 1K tokens**.
  - **Complex Tier**: Mapped to `llama_70b` (`meta-llama/llama-3.3-70b-instruct`). Cost: **$0.00013 / $0.0004 per 1K tokens** (or configurable to `gpt4o` / `claude_sonnet_4`).

- **Router Execution & Fallback** ([`src/routing/router.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/routing/router.py)):
  Calls OpenRouter via the OpenAI Python SDK compatible client. If the target model returns a 429, 5xx, or network failure, it automatically cascades to a fallback model and flags `fallback_used: true` in the audit log.

---

### 3.2 Cost & Financial Savings Engine

The financial ledger provides uncompromised transparency against **OpenAI's flagship GPT-4o** ($2.50 input / $10.00 output per million tokens).

#### The Mathematics:
For every prompt processed:
1. **Actual Answer Cost ($C_{\text{answer}}$)**:
   $$C_{\text{answer}} = (\text{Tokens}_{\text{in}} \times \text{Rate}_{\text{in}}) + (\text{Tokens}_{\text{out}} \times \text{Rate}_{\text{out}})$$
2. **GPT-4o Baseline Cost ($C_{\text{baseline}}$)**:
   $$C_{\text{baseline}} = \left(\text{Tokens}_{\text{in}} \times \frac{\$2.50}{1,000,000}\right) + \left(\text{Tokens}_{\text{out}} \times \frac{\$10.00}{1,000,000}\right)$$
3. **Verification & Arbitration Cost ($C_{\text{verification}}$)**:
   Tokens consumed by background judges and multi-critic panels.
4. **Net Dollar Saved ($S_{\text{net}}$)**:
   $$S_{\text{net}} = C_{\text{baseline}} - (C_{\text{answer}} + C_{\text{verification}})$$
5. **Percentage Saved ($S_{\%}$)**:
   $$S_{\%} = \frac{S_{\text{net}}}{C_{\text{baseline}}} \times 100$$

*Design Rule*: If an answer is heavily escalated and background verification consumes more tokens than GPT-4o would have, $S_{\text{net}}$ becomes negative. The system **never falsely clamps** negative savings to zero, preserving strict financial honesty.

---

### 3.3 Asynchronous Verification Pipeline

Implemented in [`src/verification/single_judge.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/verification/single_judge.py):
- When a prompt is served by a cheap model, FastAPI returns the streamed tokens to the user immediately.
- Concurrently, an `asyncio.create_task` triggers `_verify_async`:
  1. Requests a reference answer to the same prompt from a **Strong Model** (e.g., `openai/gpt-4o`).
  2. Submits both the candidate answer and the reference answer to a **Judge Model** (`openai/gpt-4o-mini`).
  3. The judge evaluates semantic divergence, factual accuracy, and required constraints under strict structured formatting:
     ```text
     VERDICT: AGREE | DISAGREE
     REASON: <one sentence explanation>
     ```
  4. If the judge returns `AGREE`, the request status in SQLite is marked `verified` with finalized savings.
  5. If the judge returns `DISAGREE`, the request is automatically escalated to the LangGraph Arbitration Panel.

---

### 3.4 LangGraph 3-Critic Arbitration Panel

Implemented in [`src/arbitration/graph.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/arbitration/graph.py):
When a disagreement occurs, LangGraph spins up a parallel multi-agent panel:

1. **Parallel Fan-Out (Superstep 1)**:
   - **Accuracy Critic** (`openai/gpt-4o-mini`): Scrutinizes factual assertions against reference citations.
   - **Logic Critic** (`anthropic/claude-3-haiku`): Evaluates reasoning soundness, deductive validity, and logical leaps.
   - **Completeness Critic** (`meta-llama/llama-3.3-70b-instruct`): Verifies whether all explicit user requirements and edge cases were fulfilled.
2. **Disagreement Detection (Fan-In)**:
   - Calculates score spreads across critics. If $\max(\text{scores}) - \min(\text{scores}) \ge 2$, it flags a score divergence.
   - Isolates unique issues identified by only one critic.
3. **Adjudication**:
   - The **Adjudicator** receives the prompt, candidate text, all 3 critique reports, and the list of flagged disagreements.
   - Synthesizes an overall calibrated quality score (0–10) and issues a binding verdict:
     - `should_escalate: true/false`
     - Detailed explanation and remediation suggestions.
   - Saves final verdict JSON and total arbitration costs into the database.

---

### 3.5 Data Persistence & Storage Architecture

Implemented in [`src/storage/db.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/storage/db.py) using SQLite (`data/router.db`):

#### Database Schema
- **`users` Table**:
  - `id` (UUID PK), `email`, `hashed_password`, `daily_request_limit`, `created_at`.
- **`conversations` Table**:
  - `id` (UUID PK), `user_id` (FK), `session_id`, `title`, `created_at`, `updated_at`, `deleted` (soft-delete flag).
- **`requests` Table**:
  - `id` (UUID PK): Unique identifier for each prompt-response execution.
  - `conversation_id`: Links the request to a specific conversation thread.
  - `user_id`: Enforces strict data isolation between accounts.
  - `prompt`: User input prompt text.
  - `response_text`: Complete LLM generated response.
  - `tier`: Assigned complexity tier (`simple`, `moderate`, `complex`).
  - `model_used` & `model_id`: OpenRouter model identifiers.
  - `cost_usd`: Exact token cost of the primary model.
  - `answer_cost`: Cost of initial answer generation.
  - `verification_cost`: Cumulative cost of judges and critics.
  - `baseline_cost_usd`: GPT-4o cost for identical input/output tokens.
  - `net_saved` & `saved_percent`: Real dollar and percentage savings.
  - `savings_final`: Boolean flag indicating if background verification has concluded.
  - `status`: Lifecycle state (`routed`, `verifying`, `verified`, `arbitrating`, `arbitrated`, `error`).
  - `verify_verdict`, `verify_reason`: Single-judge output.
  - `verdict_json`: Full LangGraph 3-critic breakdown.
- **`refresh_tokens` Table**:
  - `token_hash`, `user_id`, `expires_at`, `revoked`. Supports secure rotating JWT sessions.

---

### 3.6 Backend API Architecture

Implemented with **FastAPI** ([`src/api/main.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/api/main.py)):

- **Security & Multi-Tenancy** ([`src/api/deps.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/api/deps.py)):
  - JWT Access Tokens (15 min expiry) passed via `Authorization: Bearer <token>`.
  - Refresh Tokens stored in httpOnly, Secure cookies (`/v1/auth/refresh`).
  - Per-user sliding-window rate limiting (20 requests/minute default).
  - Daily request caps per user.
  - Strict user-scoping: queries always filter by `user_id = current_user.id`.
- **Real-Time Streaming** (`POST /v1/chat/stream`):
  - Streams Server-Sent Events (SSE):
    - `meta`: Sends model used, tier, and request ID.
    - `token`: Streams tokens incrementally to the browser.
    - `done`: Sends provisional financial metrics and kicks off background verification.
- **Live Status Push** (`GET /v1/requests/{id}/events`):
  - EventSource connection for the browser to observe background verification transitions (`verifying` &rarr; `arbitrating` &rarr; `final`).

---

### 3.7 Frontend Web Workspace

Built with **Next.js 16 (App Router)**, **React 19**, and **Tailwind CSS** in [`web/`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/):

- **Routes**:
  - `/login` & `/register`: Clean authentication with automated JWT refresh handling.
  - `/chat`: Main workspace with prompt suggestions, tier indicators, and conversation initiator.
  - `/chat/[id]`: Active conversation view with message history, streaming response, and real-time Quality Badges.
  - `/usage`: Executive analytics dashboard detailing lifetime dollar savings, escalation rate, model distribution charts, and daily financial audit logs.
- **Streaming Engine** ([`web/hooks/useStream.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/hooks/useStream.ts)):
  - Uses `fetch` with `ReadableStreamDefaultReader` and `TextDecoder` to parse incoming SSE events on the fly without socket overhead.

---

## 4. Problems Diagnosed & Solved (Pair Programming Session)

During our session, we resolved 3 fundamental bugs that prevented the frontend from functioning correctly:

### Bug 1: Array vs. Object Schema Mismatch Crashing the Sidebar
- **Symptom**: Runtime `TypeError: Cannot read properties of undefined (reading 'length')` at [`web/components/sidebar/Sidebar.tsx:176`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/components/sidebar/Sidebar.tsx).
- **Root Cause**: The FastAPI endpoint `GET /v1/conversations` returned a raw array (`list[dict]`), whereas `conversationApi.list()` in [`web/lib/api.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/lib/api.ts) expected an object `{ conversations: [...] }`. Accessing `data.conversations` returned `undefined`, causing `conversations.length` in the Sidebar to crash the React tree.
- **Fix**:
  - Normalized `conversationApi.list()` in [`web/lib/api.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/lib/api.ts) to handle both direct arrays and wrapped objects.
  - Added fallback guards `conversations = []` and `(conversations || []).length` in [`web/components/sidebar/Sidebar.tsx`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/components/sidebar/Sidebar.tsx).

### Bug 2: Missing Data Unpacking Causing Blank Response Bubbles
- **Symptom**: When asking a query (e.g., *"what is laptop"*), the UI only showed the "Router AI" badge and savings pill, but **no answer text and no user prompt** were visible.
- **Root Cause**: The database stores requests as single rows in the `requests` table with fields `prompt` and `response_text`. When [`web/lib/api.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/lib/api.ts) fetched `/v1/conversations/{id}/messages`, it returned these raw rows directly. However, the UI component [`MessageBubble`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/components/chat/MessageBubble.tsx) expected individual message objects with `sender: 'user' | 'assistant'` and `content: string`. Because `sender` and `content` were undefined, the prompt was discarded and the response text rendered blank.
- **Fix**:
  - Re-engineered `conversationApi.getMessages()` in [`web/lib/api.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/lib/api.ts) to unpack each database record into two distinct messages:
    1. A User Message: `{ sender: 'user', content: item.prompt }`
    2. An Assistant Message: `{ sender: 'assistant', content: item.response_text, ...metadata }`
  - Added synchronization in [`web/app/chat/[id]/page.tsx`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/app/chat/%5Bid%5D/page.tsx) to await message re-fetching upon stream completion.

### Bug 3: Raw Markdown Asterisks Instead of Formatted Bold Text
- **Symptom**: Words like `**Keyboard**` and `**Display**` were displayed with raw asterisks instead of styled bold text.
- **Root Cause**: [`MessageBubble.tsx`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/components/chat/MessageBubble.tsx) rendered `{content}` directly inside a standard HTML `<div>` without a Markdown parsing engine.
- **Fix**:
  - Installed `react-markdown` and `remark-gfm`.
  - Replaced raw text output with `<ReactMarkdown>` supporting custom Tailwind styling for bold text, lists, headers, blockquotes, and code blocks.

---

## 5. How to Run, Test, and Verify

### 5.1 Local Development

#### Terminal 1 — Backend (FastAPI on Port 8000)
```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base & Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive Swagger Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

#### Terminal 2 — Frontend (Next.js on Port 3000)
```bash
cd web
npm install
npm run dev
```
- Workspace: [http://localhost:3000/chat](http://localhost:3000/chat)
- Savings & Analytics: [http://localhost:3000/usage](http://localhost:3000/usage)

#### Terminal 3 (Optional) — Admin Dashboard (Streamlit on Port 8501)
```bash
source .venv/bin/activate
streamlit run src/dashboard/app.py
```
- Admin Dashboard: [http://localhost:8501](http://localhost:8501)

### 5.2 Docker Compose (All Services)
```bash
docker compose up --build
```

### 5.3 Automated Testing
Execute the complete test suite covering auth, data isolation, and cost calculation:
```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
*(All 28 unit and integration tests passing).*

---

## 6. Comprehensive Mastery Roadmap: How to Learn Everything in This Project

To master every layer of technology implemented in this codebase, follow this 5-stage learning progression:

### Stage 1: LLM Economics & Gateway Integration
- **Concept**: Understanding tokenomics, prompt vs. completion costs, and why multi-model gateways exist.
- **Code to Study**:
  - [`src/models/registry.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/models/registry.py): How model pricing registries are defined.
  - [`src/models/interface.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/models/interface.py): How to call OpenRouter using the unified OpenAI API schema with token tracking.

### Stage 2: Feature Engineering & Lightweight NLP Classification
- **Concept**: How to make ultra-low-latency classification decisions without paying LLM inference overhead.
- **Code to Study**:
  - [`src/routing/features.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/routing/features.py): Feature extraction using regex, lexical density, and keyword sets.
  - [`src/routing/train_classifier.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/routing/train_classifier.py): Training a scikit-learn Logistic Regression classifier with standard scalers.

### Stage 3: Async Concurrency, SSE, and FastAPI
- **Concept**: High-throughput web architectures, asynchronous generators, and Server-Sent Events.
- **Code to Study**:
  - [`src/api/main.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/api/main.py): `_stream_completion()` and `StreamingResponse(media_type="text/event-stream")`.
  - `asyncio.create_task`: Triggering background single-judge verification without blocking the user's HTTP request.
  - [`src/api/deps.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/api/deps.py): In-memory sliding-window rate limiting algorithms.

### Stage 4: Multi-Agent Systems & LangGraph
- **Concept**: State graphs, parallel agent execution (fan-out/fan-in), and jury adjudication.
- **Code to Study**:
  - [`src/arbitration/graph.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/arbitration/graph.py): Setting up `StateGraph(ArbitrationState)`, parallel edges `START -> [accuracy, logic, completeness]`, and fan-in nodes.
  - [`src/arbitration/critics.py`](file:///Users/parthagarwal/Projects/llm-router-arbitration/src/arbitration/critics.py): Prompt engineering for specialized reviewer agents.

### Stage 5: Full-Stack React 19, Next.js 16, and SSE Stream Consumption
- **Concept**: Consuming chunked streams in React, state management, and real-time Markdown rendering.
- **Code to Study**:
  - [`web/hooks/useStream.ts`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/hooks/useStream.ts): How `ReadableStreamDefaultReader` reads byte chunks and parses custom SSE events (`event: meta`, `event: token`, `event: done`).
  - [`web/components/chat/MessageBubble.tsx`](file:///Users/parthagarwal/Projects/llm-router-arbitration/web/components/chat/MessageBubble.tsx): Implementing `react-markdown` and `remark-gfm` with tailored Tailwind tokens.
