# KarzounOS — Architecture

> البنية التقنية الكاملة لمنصة KarzounOS — منصة الموظفين الرقميين.

---

## 🏗️ نظرة عامة

```
┌─────────────────────────────────────────────────────────────────┐
│                      KarzounOS Platform                         │
├────────────────────┬────────────────────────────────────────────┤
│   End Users        │         Admin Portal                       │
│                   │                                            │
│  ┌───────────┐    │  ┌──────────────────────┐                  │
│  │ Desktop   │    │  │   Next.js Admin UI   │                  │
│  │ App (.exe)│    │  │   (10 Pages)         │                  │
│  │ Electron  │    │  │   localhost:3000     │                  │
│  │           │    │  └──────────┬───────────┘                  │
│  │ WebSocket │    │             │                               │
│  │ + Heart   │    │             │                               │
│  │ beat 30s  │    │             ▼                               │
│  └─────┬─────┘    │  ┌──────────────────────┐                  │
│        │          │  │   FastAPI Backend    │                  │
│  ┌─────┴─────┐    │  │   localhost:8001     │                  │
│  │ Telegram  │    │  │                      │                  │
│  │ Bot       │    │  │  5 Routers:          │                  │
│  │           │    │  │  - health.py         │                  │
│  │ /bind     │    │  │  - auth.py           │                  │
│  │ /message  │    │  │  - chat.py           │                  │
│  └─────┬─────┘    │  │  - admin.py          │                  │
│        │          │  │  - telegram.py       │                  │
│        │          │  │                      │                  │
├────────┼──────────┤  │  + WebSocket:         │                  │
│        │          │  │  ws/chat              │                  │
│  ┌─────┴─────┐    │  └──────────┬───────────┘                  │
│  │  Celery   │    │             │                               │
│  │ Worker    │    │             ▼                               │
│  │ + Beat    │    │  ┌──────────────────────┐                  │
│  │           │    │  │   PostgreSQL 16      │                  │
│  │ reset     │    │  │   localhost:5433     │                  │
│  │ counters  │    │  │                      │                  │
│  │ cleanup   │    │  │   10 Tables:         │                  │
│  │ sessions  │    │  │   User, Profile,     │                  │
│  │ email     │    │  │   Session, Message,  │                  │
│  └─────┬─────┘    │  │   KPI, AuditLog,     │                  │
│        │          │  │   AgentTemplate,     │                  │
│        │          │  │   UserApiKey,        │                  │
│        ▼          │  │   TelegramBinding,   │                  │
│  ┌───────────┐    │  │   ProfileUser,       │                  │
│  │   Redis   │    │  │   UserActivity       │                  │
│  │ :6378     │    │  └──────────┬───────────┘                  │
│  │ Broker    │    │             │                               │
│  └───────────┘    │             ▼                               │
│                   │  ┌──────────────────────┐                  │
│                   │  │   LLM Providers      │                  │
│                   │  │                      │                  │
│                   │  │  - MiniMax (default) │                  │
│                   │  │  - OpenAI            │                  │
│                   │  │  - Ollama (local)    │                  │
│                   │  │  - Mock (testing)    │                  │
│                   │  └──────────────────────┘                  │
└────────────────────┴────────────────────────────────────────────┘
```

---

## 📦 المكونات الرئيسية

### 1. Backend — FastAPI

**التقنيات:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic

**البوابة:** `localhost:8001`

**5 رouters:**

| Router | المسار | عدد Endpoints | الوظيفة |
|--------|--------|---------------|---------|
| health | `/health` | 2 | فحص صحة النظام (DB, Redis) |
| auth | `/auth` | 5 | تسجيل دخول، تفعيل، تحديث توكن، Me |
| chat | `/chat` | 4 | إرسال رسالة، Streaming SSE، محادثات، تحديث عناوين |
| admin | `/admin` | 25+ | إدارة كل شيء: موظفين، بروفايلات، جلسات، KPIs، Audit |
| telegram | `/telegram` | 2 | Webhook Telegram، bind/unbind |
| ws/chat | `/ws/chat` | 1 | WebSocket streaming bidirectional |

**Agent Service:**
- 4 مزودين: MiniMax, OpenAI, Ollama, Mock
- Hot-swappable عبر `LlmProvider` enum
- Streaming via async generator events
- Token estimation (عربي 3 chars/token، كود 2 chars/token)
- Fernet encryption للمفاتيح الحساسة

**Security:**
- JWT Authentication (HS256, 24h expiry)
- Bcrypt password hashing
- Rate limiting (in-memory + Redis-ready)
- CORS restricted (methods + origins)
- Pydantic validation schemas على جميع admin endpoints
- Password policy (8+ chars, letter + number required)
- Self-registration closed — invite-only

### 2. Desktop App — Electron

**التقنيات:** Electron, BrowserView, IPC

**المخرجات:** `.exe` installer (NSIS, ~74MB)

**الميزات:**
- WebSocket client مع JWT validation
- Heartbeat كل 30 ثانية (`last_seen_at`)
- Telegram binding (`/bind <code>`)
- Activation screen قبل الاستخدام
- Folder scanner + project context
- KarzounOS Dark glass theme

### 3. Admin Dashboard — Next.js

**التقنيات:** Next.js 16, TypeScript, Tailwind CSS

**10 صفحات:**

| الصفحة | المسار | الوظيفة |
|--------|--------|---------|
| Dashboard | `/` | إحصائيات، Charts، Activity feed، Online users |
| Login | `/login` | تسجيل دخول الإدارة |
| Employees | `/employees` | CRUD الموظفين + الحدود |
| Profiles | `/profiles` | إدارة بروفايلات Hermes (AGENTS.md) |
| Assignments | `/assignments` | ربط البروفايلات بالموظفين |
| Sessions | `/sessions` | عرض الجلسات والمحادثات |
| Templates | `/templates` | قوالب الوكلاء |
| API Keys | `/api-keys` | مفاتيح API للموظفين + الميزانية |
| KPIs | `/kpis` | مؤشرات الأداء + التحليلات |
| Audit | `/audit` | سجل التدقيق الكامل |

**Design System:** KarzounOS (Indigo + Amber, Cairo + Inter, RTL)

### 4. Database — PostgreSQL 16

**10 جداول:**

| الجدول | الوصف | الحقول الرئيسية |
|--------|-------|----------------|
| `users` | المستخدمين | email, full_name, role, is_active, invite_token, is_activated, last_seen_at, pending_employee |
| `profiles` | بروفايلات Hermes | name, slug, soul_md, skills[], agents_md, system_prompt |
| `profile_users` | ربط البروفايلات بالموظفين | user_id, profile_id, priority |
| `sessions` | جلسات الدردشة | user_id, title, profile_id, created_at |
| `messages` | الرسائل | session_id, role (user/assistant), content, tokens_estimated, created_at |
| `kpi` | مؤشرات الأداء اليومية | user_id, date, messages_sent, tasks_completed, active_minutes, tokens_used, total_cost, models_used[] |
| `audit_log` | سجل التدقيق | user_id, action, details, ip_address, created_at |
| `agent_templates` | قوالب الوكلاء | name, department, model_name, tools[], temperature |
| `user_api_keys` | مفاتيح API | user_id, provider, key_prefix, daily_budget, spent_today |
| `telegram_bindings` | ربط التلجرام | user_id, chat_id, is_active |
| `user_activities` | تتبع النشاط | user_id, action_type, details, created_at |

**Migration:** Alembic — 2 migration files

### 5. Celery — Background Workers

**Worker:** `celery -A app.celery_app worker --pool=solo` (Windows)
**Beat:** `celery -A app.celery_app beat --schedule celerybeat-schedule.db`

**المهام:**
| المهمة | الجدولة | الوظيفة |
|--------|---------|---------|
| `reset_daily_counters` | يومياً 00:00 | تصفير quotas, tokens_spent_today, spent_today |
| `cleanup_old_sessions` | أسبوعياً | حذف الجلسات القديمة (>90 يوم) — SQL injection safe |
| `send_email_notification` | manual | إرسال بريد عبر SMTP مع TLS/SSL |

### 6. Redis — Message Broker

**البوابة:** `localhost:6378`

**الوظائف:**
- Celery broker
- Celery result backend
- Rate limiting (future Redis-backed)

---

## 🔐 تدفق المصادقة (Auth Flow)

```
1. Admin يُنشئ موظف → يتم توليد invite_token تلقائياً
2. الموظف يصل → يُرسَل له invite_token
3. الموظف يفتح Desktop → يدخل البريد + كلمة المرور + invite_token
4. نظام يُفعّل الحساب → is_activated = true
5. الموظف يدخل /bind <telegram_code> → يربط التلجرام
6. WebSocket يفتح → heartbeat كل 30 ثانية → last_seen_at يتحدّث
```

---

## 🌐 تدفق المحادثة (Chat Flow)

```
Desktop App
    │
    ├─ 1. WebSocket connect with JWT → /ws/chat?token=<jwt>
    ├─ 2. System checks: user activated? telegram bound?
    ├─ 3. WebSocket open → send "connected" event
    ├─ 4. User sends message → WS sends to backend
    ├─ 5. Backend → AgentService → LLM Provider
    ├─ 6. LLM returns chunks → WS sends "chunk" events
    ├─ 7. Done → WS sends "done" event with conversation_id
    ├─ 8. Message saved to DB → KPI updated
    └─ 9. Heartbeat كل 30 ثانية → last_seen_at updated
```

---

## 🐳 Docker Services

```yaml
docker-compose.yml
├── api       → FastAPI :8001
├── admin     → Next.js :3000
├── worker    → Celery Worker
├── beat      → Celery Beat
├── db        → PostgreSQL :5433
└── redis     → Redis :6378
```

---

## 📂 هيكلية المشروع

```
AgentSaaS/
├── app/
│   ├── api/              # Routers
│   │   ├── chat.py       # SSE + regular chat
│   │   ├── websocket_chat.py  # WebSocket endpoint
│   │   ├── admin.py      # Admin CRUD + monitoring
│   │   ├── auth.py       # JWT auth + invite flow
│   │   ├── telegram.py   # Telegram webhook
│   │   └── health.py     # Health checks
│   ├── core/             # Config, security
│   │   ├── config.py     # Settings (Pydantic BaseSettings)
│   │   └── security.py   # JWT, bcrypt, fernet
│   ├── models/           # SQLAlchemy models (11 tables)
│   ├── schemas/          # Pydantic validation schemas
│   ├── services/         # Business logic
│   │   ├── agent_service.py    # LLM provider abstraction
│   │   └── token_tracker.py    # Token usage tracking
│   ├── celery_app.py     # Celery configuration
│   ├── tasks.py          # Background tasks
│   ├── main.py           # FastAPI app + middleware
│   └── dependencies.py   # Shared dependencies
├── frontend/             # Next.js Admin Dashboard
│   ├── src/app/          # Pages (10 routes)
│   ├── src/components/   # Shared components (sidebar, etc.)
│   ├── src/lib/          # API client, types
│   └── src/app/globals.css  # KarzounOS design tokens
├── desktop/              # Electron app
│   ├── src/main/         # Main process
│   ├── src/renderer/     # UI (WebSocket client)
│   └── dist/             # Built app
├── migrations/           # Alembic migrations
├── tests/                # Pytest (67 tests)
├── docker-compose.yml    # All services
├── Dockerfile            # API container
├── Dockerfile.admin      # Admin container
├── Dockerfile.worker     # Worker container
├── .env.example          # Environment template
├── DESIGN_SYSTEM.md      # Design guidelines
├── ARCHITECTURE.md       # This file
├── CUSTOMER_JOURNEY.md   # Customer journey
├── CURRENT_STATUS.md     # Achievement status
└── DESIGN_PLAN.md        # Implementation plan
```
