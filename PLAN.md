# PLAN.md — Mac mini Personal Automation Assistant (Telegram + Mail + Calendar + Monitoring)

## 0) Purpose
Build a **personal automation assistant** running on my Mac mini that:
1) Summarizes **Gmail + School Outlook** emails
2) Detects **important items** (deadlines / meetings / required actions)
3) Creates/updates **calendar events automatically**
4) Sends concise **Telegram notifications**
5) Runs continuously as a **personal server** (always-on automation runner)

This document is the **source of truth** for requirements, constraints, decisions, and interaction rules.

---

## 1) Current Scope (MVP)
### 1.1 Telegram → Calendar (Natural Language)
- User sends a message in Telegram describing an appointment
- System parses it into a structured event
- If confident → **auto-create event**
- If ambiguous → ask **ONE confirmation question**
- Default event duration if end-time missing: **60 minutes**
- Timezone default: **America/Toronto**
- Output: a 1-line receipt message (event title + date + start/end + reminder)

### 1.2 Mail → Summary → Action Extraction
- Periodically pull unread/new messages from:
  - Gmail (personal)
  - Outlook (school)
- For each email thread: produce:
  - 1–3 line summary
  - Action items (if any)
  - Deadlines / dates / meeting times (if any)
- If important event detected → create calendar event OR send “needs confirmation” message in Telegram

### 1.3 Monitoring → Digest → Alerts
- Monitor selected sources (later section defines exact sources)
- Summarize and send alerts only when:
  - matches tracked topics
  - passes importance threshold

---

## 2) Non-Goals (Explicitly Out of Scope for MVP)
- Full “smart home” control or device automation
- Complex multi-agent workflows
- Auto-responding to emails without explicit approval (unless later added)
- High-frequency trading or sensitive financial automation
- Advanced UI (web dashboard) beyond basic logs/admin endpoints

---

## 3) Interaction & Customization Rules (Me + Assistant Working Style)
These are rules for planning/implementation discussions and for how the assistant should behave.

### 3.1 Communication / Planning Style
- Prefer: **core conclusion first**, then brief reasoning
- Avoid: vague guesses; if uncertain, state uncertainty and assumptions
- Focus on: reusable patterns, failure cases, edge cases
- When discussing implementation: provide concrete steps and explicit trade-offs
- Avoid unnecessary emotional tone or over-praise

### 3.2 No Over-Generalization Rule
- Don’t generalize “in theory”; map advice to **this system’s actual components**
- When proposing steps, include:
  - what changes
  - where it runs
  - failure modes
  - how to validate it

### 3.3 Confirmation Policy (Calendar Creation)
- Mode: **B**  
  - If confidence high → create automatically
  - If ambiguous → ask **ONE** confirmation question
- Default duration: **60 minutes** if end time missing

---

## 4) System Architecture (High-level)
### 4.1 Components
- **Telegram Bot**: user-facing interface (commands + natural language)
- **Automation Runner** (Mac mini):
  - Receives Telegram messages
  - Polls email/feeds
  - Calls LLM API for parsing/summarization
  - Writes logs + state
  - Creates/updates calendar
- **LLM**:
  - Use cloud API initially (Claude/GPT/etc.)
  - Local LLM optional later (not required)

### 4.2 Data Stores
- `state.db` (SQLite) for:
  - processed message IDs
  - dedupe keys
  - calendar event mapping
  - last run times
- `logs/` for:
  - structured logs (JSONL)
  - error traces

### 4.3 Deployment
- Always-on process on Mac mini via:
  - launchd service OR Docker Compose (choose later)
- Secrets stored in:
  - macOS Keychain OR `.env` + restricted permissions (choose later)

---

## 5) Calendar Integration Strategy (Decision Pending)
Two stable options:

### Option A — CalDAV (preferred for long-term stability)
- Create/update/read events via CalDAV
- Works well if calendar is iCloud/Google synced into Apple Calendar

### Option B — AppleScript (fast PoC, more fragile)
- Create events by scripting the Calendar app
- Potential issues: permissions, foreground app state, macOS updates

**MVP Decision Goal**:
- Prefer stability for always-on server usage → likely **CalDAV** unless blocked.

---

## 6) Telegram UX Spec
### 6.1 Natural Language Examples
- "이번주 금요일 3시 팀미팅 일정 추가"
- "내일 11:30 치과 예약, 알림 2시간 전"
- "3/8 오후 2~4시 스터디"

### 6.2 Commands (Minimal set)
- `/add ...` force-add with explicit fields (fallback)
- `/today` show today’s agenda
- `/week` show this week’s agenda
- `/help` show examples

### 6.3 Receipt Format (1-liner)
- ✅ Added: `YYYY-MM-DD (Day) HH:MM–HH:MM Title (Reminder Xm)`
- If needs confirmation:
  - `확인: YYYY-MM-DD HH:MM–HH:MM Title 맞아? (1) OK (2) 시간수정 (3) 날짜수정`

---

## 7) Email Spec
### 7.1 Sources
- Gmail: via Google API
- Outlook (School): via Microsoft Graph API

### 7.2 Output format (Telegram)
For each important email:
- Subject + 1–2 line summary
- "Action:" list (max 3 bullets)
- "Deadline/Time:" if detected
- If calendar event suggested: include parsed event preview + ask confirm if uncertain

### 7.3 Importance Heuristics (Initial)
Mark as important if any:
- sender is in allowlist (school/professor/domain)
- contains keywords: due, deadline, assignment, quiz, midterm, meeting, schedule, appointment
- contains explicit date/time pattern

---

## 8) Monitoring Spec (Digest + Alerts)
### 8.1 Sources (Decision Pending)
- RSS feeds (news sites)
- Twitter/X (keyword-based)
- Stocks/crypto watchlist (price alerts + news)

### 8.2 Alert Rules
- Avoid spam:
  - cap messages per day (e.g., <= 10)
  - dedupe similar headlines
- Send only if:
  - matches tracked topics AND
  - novelty score high OR source priority high

### 8.3 Digests
- Optional daily digest at fixed time (e.g., 09:00 Toronto)

---

## 9) Security / Safety Constraints
- Never store raw credentials in repo
- Log redaction for tokens
- Email content stored minimally (only what needed for dedupe + summary)
- No automatic sending of emails unless explicitly enabled later
- Calendar changes:
  - every created event must be traceable to a message/email ID in state.db

---

## 10) Cost Controls
- LLM usage:
  - limit tokens per request
  - summarize long emails with staged approach
- Daily hard caps:
  - max LLM calls per day
  - max alerts per day
- Optional “dry-run mode”:
  - parse + preview but do not write to calendar

---

## 11) Validation & Testing
### 11.1 Unit tests
- date parsing
- timezone conversion
- dedupe logic
- event JSON schema validation

### 11.2 End-to-end tests
- Telegram message → event created in Apple Calendar
- Email thread → summary + action extracted + optional event preview

### 11.3 Observability
- structured logs
- error notifications to Telegram (admin only)

---

## 12) Milestones (Execution Plan)
### Milestone 1 — Telegram Bot Skeleton
- Receive messages
- Reply with echo + help
- Store message IDs in SQLite

### Milestone 2 — Calendar Create (Dry-run first)
- Parse messages into event JSON
- Implement confirmation logic (B mode)
- Create events in calendar (or dry-run preview)

### Milestone 3 — Gmail Integration
- OAuth setup
- Pull unread
- Summarize + action extraction
- Notify Telegram

### Milestone 4 — Outlook Integration
- Microsoft Graph auth
- Same pipeline as Gmail

### Milestone 5 — Monitoring MVP
- RSS sources
- Summarize + alerts + daily digest

---

## 13) Open Decisions (To be finalized with assistant)
1) Calendar backend: CalDAV vs AppleScript
2) Notification channel: Telegram only (yes for MVP)
3) Where secrets live: Keychain vs .env
4) Whether to run as:
   - launchd service
   - Docker compose
   - tmux + manual (not preferred long-term)
5) Confirmation behavior for email-derived events:
   - always confirm
   - confirm only if ambiguous (align with B policy)

---

## 14) Glossary
- **B mode**: Auto-create when confident; otherwise ask one confirmation
- **Receipt**: Telegram 1-line confirmation message after event creation
- **Dedupe**: Avoid duplicate event creation from repeated messages/emails
