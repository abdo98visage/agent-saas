# 🔍 تقرير تدقيق شامل — AgentSaaS (FQ-SaaS)

**التاريخ:** 2026-06-22
**النطاق:** مراجعة الكود البرمجي الفعلي (Python Backend, API, Services, Models, Tests, Desktop, Telegram)
**المنهجية:** قراءة مباشرة للملفات البرمجية — لا اعتماد على ملفات `.md`

---

## 📊 ملخص سريع

| المقياس | القيمة |
|---------|--------|
| ملفات Python | 74+ |
| endpoints | 42+ |
| نماذج DB | 14 جدول |
| مشاكل Critical | 7 |
| مشاكل High | 7 |
| فجوات Production (Medium) | 5 |
| تحسينات (Low) | 5 |

**التقييم العام:** المنصة قوية كـ concept — الـ architecture متعدد المستخدمين مع profiles والـ Hermes integration ممتازة. لكن الفجوات بين الحالي والـ production-ready كبيرة، خاصة في البنية التحتية والأمان.

---

## 🚨 Critical — مشاكل أمنية خطيرة

### 1. كشف Invite Token في API Response

**الملف:** `app/api/admin.py:131-136`

```python
return {
    "id": str(user.id), "email": user.email,
    "invite_token": invite_token,  # ← مكشوف!
    "message": "Employee created. Share invite token..."
}
```

**المخاطر:** التوكين يُعرض في response الـ API للـ admin. لو كان هناك XSS أو data breach، أي موظف يقدر يفتح حسابات جديدة.

**الحل:** إرجاع `has_invite_token: true` فقط. التوكين يُعرض مرة واحدة في admin UI ولا يُعاد في API calls.

---

### 2. Default Password عند إنشاء الموظفين

**الملف:** `app/api/admin.py:114-116`

```python
user = User(
    email=req.email,
    hashed_password=get_password_hash("default123"),  # ← كلمة مرور افتراضية
```

**المخاطر:** الموظف يُنشأ بـ password معروف. الفترة بين الإنشاء والتفعيل فيها خطر — لو سُرق الـ invite token قبل التفعيل، المهاجم يستخدم `default123`.

**الحل:** لا تحفظ أي hashed_password عند الإنشاء. اجعل الـ activation endpoint إلزامي لتعيين password.

---

### 3. Race Condition في الـ Quota Checks (TOCTOU)

**الملفات:** `app/services/token_tracker.py`, `app/api/chat.py:48-58`

```python
# في chat.py:
if not await check_request_quota(db, str(user.id), user.max_requests_per_day):
    raise HTTPException(status_code=429, ...)
# ← Gap: بين الـ check والـ record، طلبات متعددة قد تمر
await record_token_usage(db, ...)
```

**المخاطر:** الـ check والـ record مش atomic. في حمل عالي، طلبات متعددة تمر الـ check قبل ما أي واحد يسجل usage = تجاوز الكوتا.

**الحل:** استخدم Redis atomic ops (`INCR` + `EXPIRE`) أو DB-level `SELECT FOR UPDATE` قبل الـ quota check.

---

### 4. No Token Revocation (Logout ضعيف)

**الملف:** `app/api/auth.py:201-210`

```python
@router.post("/logout")
async def logout(...):
    user.token_version = int(user.token_version or 0) + 1
    response.delete_cookie("access_token", path="/")
```

**المخاطر:** الـ token version mechanism موجود لكن JWTs ما ليها revoke list. لو سرق التوكين، يظل عامِل حتى يطلع من صلاحيتو (8 ساعات = 480 دقيقة).

**الحل:** قلّل `access_token_expire_minutes` لـ 15-30 دقيقة في production. أضف refresh token mechanism مع token blacklist في Redis.

---

### 5. Telegram `/send/{chat_id}` بدون حماية

**الملف:** `app/api/telegram.py:185-193`

```python
@router.get("/send/{chat_id}")
async def send_telegram_message(chat_id: int, text: str = ""):
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return await _send_telegram_message(chat_id, text)
```

**المخاطر:** endpoint عام بدون auth — أي واحد يقدر يبعت رسائل عبر البوت لأي chat_id!

**الحل:** أضف `Depends(get_current_admin_user)` أو احذف الـ endpoint بالكامل.

---

### 6. No Rate Limiting على Admin Endpoints

**الملف:** `app/api/admin.py` (كل الـ endpoints)

**المخاطر:** كل الـ admin endpoints (`/admin/employees`, `/admin/profiles`, etc.) بدون rate limiting. هجوم Brute-force أو scraping ممكن.

**الحل:** طبّق الـ rate limiting middleware على `/api/admin/*` بمحدودية أدق (مثلاً 30 request/دقيقة).

---

### 7. HTTP Clients بدون Connection Pooling

**الملف:** `app/services/agent_service.py:751,816,844,878,902`

```python
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(...)
```

**المخاطر:** كل request يفتح connection جديد. في load عالي = connection exhaustion + latency.

**الحل:** أنشئ httpx.AsyncClient كـ module-level singleton مع `limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)`.

---

## ⚠️ High — مشاكل هيكلية

### 8. Missing Dockerfile, docker-compose.yml, requirements.txt

**الحالة:** التستات تتوقع وجود هذه الملفات (`test_code_verification.py:285-300`) لكن مش موجودين!

**المخاطر:** مشروع بـ 42+ endpoint بدون deployment artifacts. ما تقدر تـ deploy بدون بناء كل شي يدوياً.

---

### 9. Celery Tasks على Windows ما هيعملوا في Production

**الملف:** `app/celery_app.py:18-19`

```python
if sys.platform == "win32":
    celery_app.conf.update(task_always_eager=False, worker_pool="solo")
```

**المخاطر:** `solo` pool = single-process. في Linux production، الـ async tasks هيتعطلو بسبب event loop conflicts مع psycopg3.

**الحل:** استخدم `worker_pool="prefork"` في Linux مع event loop policy. أو انتقل لـ Celery conda/uvicorn worker.

---

### 10. Database Session Leak في WebSocket

**الملف:** `app/api/websocket_chat.py:636-673`

```python
async with async_session.begin() as db:
    stream = agent_service.run_agent_stream(db=db, ...)
    async for chunk in stream:
        # ← الـ session يبقى مفتوح 30+ ثانية!
```

**المخاطر:** الـ DB connection pool حجمه 20. لو 20 مستخدم WebSocket streaming في نفس الوقت = pool exhausted = جميع الـ queries تتعطل.

**الحل:** أغلق الـ session بعد ما تخلص من الـ setup. استخدم sessions منفصلة للـ recording بعد الـ stream.

---

### 11. No Input Sanitization / Prompt Injection Protection

**الملفات:** `app/api/chat.py`, `app/api/websocket_chat.py`

**المخاطر:**
- `project_context` يُدخل مباشرة للـ LLM بدون validation
- `agents_md` و `soul_md` حتى 50KB كل واحد — يقدر يكون prompt injection
- ما في content-length limit فعلي على الرسائل

**الحل:** أضف input validation على project_context (مثلاً max 5000 char). استخدم system prompt guardrails.

---

### 12. Audit Log ناقص (بدون IP)

**الملف:** `app/models/audit_log.py` + `app/main.py:94`

```python
# middleware يحسب الـ IP لكن ما يمرره للـ audit log:
client_ip = request.client.host if request.client else "unknown"
# audit_log.ip_address = None دائماً!
```

**الحل:** مرّر الـ IP عبر request state أو dependency injection للـ audit log.

---

### 13. Token Estimation غير دقيق (±30-50%)

**الملف:** `app/services/agent_service.py:933-951`

```python
return max(1, len(text) // 4)  # English
return max(1, len(text) // 3)  # Arabic
```

**المخاطر:** chars ÷ 4 مش tokens. الخطأ 30-50% يعني الـ cost calculation و quota tracking غير دقيقين. في billing = خسارة مالية أو شكوى عملاء.

**الحل:** استخدم `tiktoken` أو `anthropic-tokenizer` لحساب tokens فعلي. أو اعتمد على الـ usage response من الـ LLM provider.

---

### 14. Cleanup Task غير فعال (O(n) deletes)

**الملف:** `app/tasks.py:76-86`

```python
for session_id in old_session_ids:
    await session.execute(delete(Message).where(Message.session_id == session_id))
    await session.execute(delete(Session).where(Session.id == session_id))
```

**المخاطر:** 10,000 session قديم = 20,000 queries.

**الحل:** استخدم CASCADE delete أو bulk `DELETE FROM messages WHERE session_id IN (...)`.

---

## 🔧 Medium — فجوات Production

### 15. No Graceful Shutdown

ما في signal handler لـ SIGTERM/SIGINT. الـ WebSocket connections والـ running requests هينقطعوا بدون إنذار.

### 16. No Retry Logic لـ External Calls

```python
response = await client.post(...)
response.raise_for_status()
```

بدون retry — أي transient network error = user-facing 500.

### 17. Sentry Conditional Import

```python
try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # ← بصمت!
```

لو Sentry ما install، التطبيق يعيط بصمت. في production = zero observability.

### 18. No Database Indexes على الـ Quota Queries

الـ queries في `_enforce_profile_request_limit` تاخد `AgentRun.created_at >= today_start` بدون index على `(profile_id, created_at)` = full table scan.

### 19. KPI Date كـ String مش DateTime

```python
date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
```

يسجل كـ `"2025-01-15"` — صعب الـ reporting والـ date range queries.

---

## 📋 Low — تحسينات

| # | المشكلة | الملف |
|---|---------|-------|
| 20 | No Pagination (offset/cursor) في list endpoints | `app/api/admin.py` |
| 21 | Inline Imports (داخل الدوال) |多处 |
| 22 | No API Versioning (`/v1/`) | `app/main.py` |
| 23 | Desktop App: Hardcoded localhost | `desktop/src/renderer/index.html:468` |
| 24 | No Request Timeout على Agent calls (Hermes) | `app/services/agent_service.py` |

---

## 🧪 حالة الاختبارات

| النوع | الحالة |
|-------|--------|
| Model field verification | ✅ موجود |
| JWT create/decode | ✅ موجود |
| Password hash | ✅ موجود |
| Endpoint path verification | ✅ موجود |
| Integration tests (TestClient) | ❌ مفقود |
| Async DB tests | ❌ مفقود |
| WebSocket tests (actual) | ❌ مفقود |
| Rate limiting tests | ❌ مفقود |
| Auth flow tests | ❌ مفقود |
| Quota enforcement tests | ❌ مفقود |

---

## 🎯 الأولويات الموصى بها (بالترتيب)

### المرحلة 1: Security Patch (فوري)
1. احذف `invite_token` من API response
2. أغلق `/send/{chat_id}` بدون auth
3. ضيف rate limiting على `/api/admin/*`
4. httpx.AsyncClient كـ module-level singleton مع connection pooling

### المرحلة 2: Infrastructure (قبل أي deployment)
5. أنشئ `Dockerfile` + `docker-compose.yml` + `requirements.txt`
6. Graceful shutdown signal handlers
7. Retry logic على external calls (exponential backoff)

### المرحلة 3: Reliability
8. Atomic quota checks (Redis INCR أو DB SELECT FOR UPDATE)
9. DB session management في WebSocket (أغلق بعد setup)
10. Database indexes على `(profile_id, created_at)` لـ AgentRun

### المرحلة 4: Accuracy & Observability
11. Token estimation بـ `tiktoken` بدلاً من chars ÷ 4
12. Audit log مع IP address
13. Sentry كـ required dependency (مش optional)

### المرحلة 5: Testing
14. Integration tests على auth flow + agent calls
15. WebSocket connection tests
16. Rate limiting enforcement tests

---

## 📝 ملاحظات نهائية

المنصة كـ concept قوية جداً:
- ✅ Multi-user isolation مع profiles ممتازة
- ✅ Hermes orchestrator integration فكرة ذكية
- ✅ Token tracking و pricing mechanism موجود
- ✅ WebSocket + SSE streaming
- ✅ Invite-based employee onboarding
- ✅ Telegram bot integration
- ✅ Alert system مع email notifications
- ✅ Audit logging framework

لكن الـ gap بين الحالي والـ production-ready يحتاج ~2-3 أسابيع عمل مكثف لإغلاق الفجوات الأمنية والبنية التحتية.
