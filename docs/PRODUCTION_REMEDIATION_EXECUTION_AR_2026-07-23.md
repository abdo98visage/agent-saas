# سجل تنفيذ معالجة جاهزية AgentSaaS للإنتاج

**تاريخ التنفيذ:** 2026-07-23  
**الخطة المرجعية:** `docs/PRODUCTION_SOLUTION_REVIEW_AR_2026-07-16.md`  
**النطاق:** Agent Runtime، FastAPI Dashboard، Desktop Application، وقنوات REST/WebSocket/Telegram  
**قيد التنفيذ:** لم تُجرَ أي إعادة تصميم أو تغيير مقصود في الثيم أو تجربة الواجهة، ولم تُستبدل الوظائف الأساسية.

---

## 1. النتيجة التنفيذية

تم تنفيذ المعالجات البرمجية الآمنة التي لا تحتاج مفاتيح إنتاج أو بنية خارجية، مرحلةً بعد مرحلة، مع التحقق بعد كل مرحلة. نجحت بوابة E2E النهائية من قاعدة بيانات فارغة وشملت:

- بناء صور API وDashboard وHermes Runtime.
- تشغيل PostgreSQL وRedis وmigration job وWorker وBeat.
- readiness للخدمات.
- تسجيل admin وضبط pricing.
- إنشاء Profile ومفتاح على مستوى Profile.
- إنشاء موظف وإسناد Profile وتفعيل الحساب.
- تنفيذ رسالة فعلية عبر Hermes.
- إصدار تذكرة WebSocket أحادية الاستخدام.
- التحقق من session/run events وKPI وusage وalerts.

النتيجة الحالية ليست إعلان `Production Go` تلقائياً؛ بقيت بوابات تعتمد على صلاحيات أو قرارات تشغيلية خارج المستودع، إضافة إلى ثلاث فجوات معمارية لا يصح إغلاقها بتخمين يغيّر سلوك المنصة: الحجز الذري المسبق للتوكنات، streaming الحقيقي من Hermes CLI، وسياسة egress/toolsets للـRuntime.

---

## 2. ما نُفذ حسب المراحل

### المرحلة 0 — احتواء الأسرار

| البند | الحالة | التنفيذ |
|---|---|---|
| منع تتبع ملفات التاريخ وبيانات PostgreSQL | مكتمل | تحديث `.gitignore` وإزالة `.history` وبيانات PostgreSQL المؤقتة من index مع إبقاء الملفات المحلية دون حذف |
| التحقق من الملفات الحساسة المتتبعة | مكتمل للنسخة الحالية | `git ls-files` لا يعيد ملفات المسارات المستهدفة |
| تقليل أسرار Runtime | مكتمل | لم يعد Runtime يستقبل `.env.production` كاملة، وأصبحت بيئة subprocess allowlist |
| تشغيل Runtime بأقل صلاحية | مكتمل | مستخدم UID 10001، filesystem read-only، tmpfs، إسقاط capabilities، `no-new-privileges` وحدود موارد |
| تدوير المفاتيح التاريخية | خارجي | يحتاج وصول مالك Supabase/مزودي الإنتاج |
| تنظيف Git history وإلزام المستنسخين بإعادة المزامنة | خارجي | عملية destructive وتؤثر على جميع الفروع والمستنسخين؛ لم تُنفذ دون تفويض صريح |
| تقييد egress للـRuntime | يحتاج قرار | Compose يعزل الأسرار والصلاحيات، لكن لا توجد allowlist شبكية على مستوى المضيف/الجدار الناري |

### المرحلة 1 — موانع الإصدار

| البند | الحالة | التنفيذ |
|---|---|---|
| Alembic head واحد | مكتمل | إصلاح سلسلة الترحيلات وإضافة `scripts/check_migration_heads.py` وبوابة CI |
| Desktop access/refresh session | مكتمل | refresh token دوّار، hash فقط في DB، إبطال الجلسات، وتخزين Desktop عبر `safeStorage` |
| WS ticket | مكتمل للإنتاج | تذكرة قصيرة وأحادية الاستهلاك في Redis؛ fallback محلي للتطوير فقط، والإنتاج يرفض البدء دون Redis |
| فرض سياسة أدوات Cowork | مكتمل ضمن عقد Cowork | allowlist وموافقة server-side، والعميل لا يستطيع ترقية `approval_mode` |
| symlink/junction containment | مكتمل | فحص real path واختبار Windows للـtraversal والـjunction |
| Hermes subprocess غير حاجب | مكتمل | `asyncio.create_subprocess_exec`، timeout، cancellation وقتل العملية |
| true token streaming | غير مكتمل | النقل أصبح async وصادقاً في final state، لكن Hermes `oneshot` لا يقدّم token stream؛ لا يمكن ادعاء TTFT حقيقي |
| صور الإصدار immutable | مكتمل كعقد نشر | release Compose يرفض غياب version/digest، والـinstaller يرفض `latest` |
| registry digests والتوقيع الفعلي | خارجي | يحتاج registry، مفاتيح توقيع، ونسخة إصدار منشورة |

ملاحظة Runtime: أزيل الخيار الصريح `--yolo`. وضع Hermes `--oneshot` نفسه غير تفاعلي ويذكر في CLI أنه يتجاوز الموافقات؛ لذلك بقي Runtime داخل حاوية محدودة الأسرار والصلاحيات ومجلد مؤقت. فرض toolsets دقيقة أو egress allowlist يحتاج تحديد القدرات التي يجب أن تبقى متاحة لكل Profile حتى لا تتغير الوظائف الأساسية.

### المرحلة 2 — سلامة الوظائف والبيانات

| البند | الحالة | التنفيذ |
|---|---|---|
| هوية الرسالة عبر القنوات | مكتمل للعيوب المحددة | `client_message_id` وunique constraint وACK بعد الحفظ، مع إعادة replay للعناصر غير المنجزة فقط |
| REST history | مكتمل | يعيد أحدث الرسائل بترتيب صحيح |
| Attachments | مكتمل داخل النشر الحالي | تحقق base64 وmagic bytes وMIME والحجم والعدد؛ تخزين blob على volume وJSONB metadata فقط؛ رابط HMAC قصير العمر |
| تمرير الصورة إلى Runtime | مكتمل | الصورة تُفك وتُرحّل مؤقتاً داخل Workspace المعزول وتُضاف لعقد الطلب |
| KPI uniqueness | مكتمل | قيد `(user_id, date)` وترحيل يدمج الصفوف السابقة |
| request quota ذرية | مكتمل | PostgreSQL upsert مشروط |
| token quota ذرية بالحجز والتسوية | يحتاج قرار | التسجيل ذري بعد الاستهلاك، لكن لا يوجد reserve مسبق؛ تحديد مقدار الحجز يغيّر سياسة الحصة |
| provider/message identity | مكتمل | القياس يستخدم هوية المزود/المفتاح والرسالة المحفوظة |
| Profile/Skill sync | مكتمل | staging وatomic rename وrollback، وفشل صريح عند غياب تعريف Skill بدلاً من placeholder |
| provider key contract | مكتمل | فصل `None` عن الإزالة/التحديث ومزامنة صحيحة |
| Admin error contract | مكتمل | تعارضات DB تعيد 409 بمرجع آمن، ومرشحات التاريخ غير الصالحة تعيد 422 |
| Telegram webhook/binding/session/metering | مكتمل | secret إلزامي عند التفعيل، ربط آمن، session مستمرة، وحصة وقياس |
| Offline queue | مكتمل | conversation/profile context immutable وclient UUID وتشفير queue |
| Atomic file apply | مكتمل | nonce وTTL وhash وpreconditions وatomic replace وrollback |
| توحيد كل القنوات داخل application service واحد | جزئي | عولجت فروق الهوية والحصة والقياس؛ إعادة بناء كل المسارات كـtransactional service/outbox أُبقيت تحسيناً معمارياً لاحقاً لتجنب over-engineering |

التخزين الحالي للـattachments هو blob filesystem دائم خارج قاعدة البيانات. الانتقال إلى S3/MinIO خارجي يحتاج اختيار خدمة وretention وcredentials، لكنه لم يعد يخزن base64 داخل JSONB للرسائل الجديدة.

### المرحلة 3 — التشغيل والاعتمادية

| البند | الحالة | التنفيذ |
|---|---|---|
| readiness حقيقية | مكتمل | DB/Redis/Orchestrator/Runtime مع deadlines قصيرة؛ production يتطلب Runtime |
| timeout alignment | مكتمل | API، Orchestrator وRuntime تستخدم حدوداً متوافقة ولا توجد طلبات `timeout=None` |
| stale runs | مكتمل | مهمة دورية تنهي runs العالقة |
| Presence متعدد النسخ | مكتمل | Redis counters مع TTL/heartbeat وLua decrement؛ memory fallback للتطوير فقط |
| Celery broker/alerts | مكتمل | broker من الإعداد الصحيح، retry exponential، وعدم تسجيل notification قبل نجاح الإرسال |
| Dashboard stats | مكتمل | aggregate query واحدة بدلاً من حلقات يومية متسلسلة |
| logging/error leakage | مكتمل | لا prompt/message preview، وإرجاع correlation reference بدل exception داخلي |
| CI | مكتمل كأساس قابل للتشغيل | Backend DB/Redis/migrations/tests، frontend lint/build، Desktop Windows/macOS tests، بناء الصور، Trivy للصور الثلاث، Gitleaks |
| Desktop release gate | مكتمل في مسار macOS | `release:check` داخل workflow الإصدار الذي يستقبل URL ومفاتيح التوقيع، وليس داخل PR بلا أسرار |
| container hardening | مكتمل لخدمات التطبيق | production وrelease: read-only، tmpfs، إسقاط capabilities، no-new-privileges وحدود CPU/RAM/PIDs |
| migration job مستقل | مكتمل | API يبدأ بعد نجاح migration one-shot، وليس migration داخل كل replica |
| ملكية volumes | مكتمل | `storage-init` يضبط ملكية attachments/profiles للمستخدم غير root |
| dependency pinning | مكتمل للـPython المباشر | Hermes `0.19.0` وCryptography المتوافق `46.0.7` واعتماد Anthropic الاختياري `0.87.0` في Runtime |
| نسخ احتياطي Linux | مكتمل برمجياً | GPG public-key encryption لقاعدة البيانات وProfiles وAttachments، manifest hashes، ولا تُنسخ env secrets |
| Restore Linux | مكتمل برمجياً | استيراد إلى DB مؤقتة، تحقق Alembic، swap بعد النجاح، staging للملفات والاحتفاظ بنسخة rollback |
| Restore drill وRPO/RTO | خارجي | يحتاج بيئة فارغة ومفتاح GPG وخطة توقف مقبولة |
| PowerShell backup/restore parity | غير مكتمل | المسار المحصّن المعتمد هو Linux installer؛ سكربتا PowerShell القديمان لم يُعاد تصميمهما |
| SLO/load/soak/chaos | خارجي | يحتاج عدد مستخدمين مستهدفاً، SLO، ميزانية provider، ونافذة اختبار |
| image signing/SBOM | خارجي | CI يبني ويفحص الصور لكنه لا يملك registry أو مفاتيح Cosign |

---

## 3. العيوب الوظيفية التي أُغلقت

- Dashboard لم يعد يخزن JWT في `localStorage` أو `window.name`؛ يستخدم HttpOnly cookie وCSRF double-submit.
- lockout أصبح حالة DB فعلية بدلاً من رسالة rate-limit مضللة.
- Desktop يجدد الجلسة دون إعادة استخدام invite.
- Offline replay لا ينتقل إلى المحادثة المفتوحة لاحقاً ولا يكرر الرسالة المحفوظة.
- updater لا يفرض التثبيت فور التنزيل، ويمنع restart عند وجود تغييرات/رسائل معلقة.
- activation URL يُنشأ من origin الخادم الموثوق بدلاً من localhost أو origin يختاره الرابط.
- Telegram لا يقبل webhook غير موثق عند تفعيل البوت، ويحافظ على الجلسة والقياس.
- Profile sync لا يكتب النسخة العاملة جزئياً ولا ينشئ Skill عامة بديلة.
- readiness لا تعلن الأخضر عند تعطل dependency أساسية.
- alert لا يُعد مرسلاً عند نجاح queue فقط.
- المرفقات الجديدة لا تضخم JSONB ببيانات base64.
- الاستهلاك يُنسب للمزود والمفتاح والرسالة الفعلية.
- Hermes Runtime image تتضمن اعتماد Anthropic الاختياري اللازم لمسار Minimax.

---

## 4. الترحيلات الجديدة

تسلسل الرأس النهائي هو:

`add_message_attachments` → `add_auth_sessions` → `add_kpi_user_date_unique` → `harden_telegram_bindings` → `add_message_idempotency` → `add_account_lockout`

الترحيلات تضيف:

- metadata للمرفقات.
- refresh sessions دوّارة.
- unique KPI يومية.
- session وربط Telegram محصّن.
- idempotency لمراسلات Desktop.
- lockout دائم للحساب.

تمت ترقية قاعدة PostgreSQL فارغة إلى الرأس ضمن E2E بنجاح.

---

## 5. نتائج التحقق النهائية

| الفحص | النتيجة |
|---|---|
| Python compileall | نجح |
| Alembic head checker | نجح، `add_account_lockout` رأس وحيد |
| Pytest داخل صورة Python 3.11 | `8 passed` |
| Attachment validation/signature tests | نجحت |
| Desktop JS syntax | نجح |
| Desktop unit test | `1 passed` لمسارات traversal/symlink/junction |
| PowerShell parser | نجح لسكربتات E2E/smoke/backup/restore |
| Bash `-n` داخل Linux | نجح لسكربتات install/backup/restore/readiness/smoke |
| Frontend ESLint | بلا أخطاء؛ تحذير React Hook سابق واحد |
| Frontend production build | نجح، TypeScript و16 صفحة static |
| Docker image build | نجح للـAPI وDashboard وHermes Runtime |
| Production/Release/E2E Compose config | نجح |
| Docker E2E fresh rebuild | نجح بالكامل |
| `git diff --check` | نجح |
| Desktop strict release check محلياً | فشل متوقع: لا public URL ولا signing secrets في بيئة التطوير |

رحلة E2E النهائية أعادت `Smoke journey passed`، وHermes status كان `running`، وسُجل usage فعلي.

---

## 6. قرارات أو صلاحيات لازمة قبل `Production Go`

1. تدوير مفاتيح Supabase/أي أسرار ظهرت في التاريخ، ثم تزويد تاريخ الإبطال.
2. تفويض rewrite كامل لتاريخ Git وإجبار جميع المستنسخين على إعادة المزامنة، أو قبول بقاء الأسرار الملغاة في التاريخ.
3. اختيار سياسة Runtime:
   - toolsets مسموحة لكل Profile؛
   - وجهات egress المسموحة؛
   - هل يُسمح للـAgent بالويب/browser/terminal أم Cowork mediation فقط.
4. تحديد سياسة token reservation: قيمة ثابتة، `max_output_tokens` للنموذج، أم حصة soft تسمح بتجاوز طلب واحد.
5. اعتماد حل streaming: Hermes server/API يدعم events، أو قبول final-chunk semantics الحالية.
6. اختيار S3/MinIO/volume للمرفقات وسياسة retention والحذف.
7. توفير registry/digests وCosign/SBOM، ومفاتيح Windows/macOS signing وupdate feed manifest.
8. توفير GPG public key خارج المضيف، وتنفيذ restore drill وتوثيق RPO/RTO.
9. تحديد SLO وعدد المستخدمين المتوقع لاختبارات load/soak/chaos.
10. اعتماد migration مستقلة لتحويل المال إلى `NUMERIC` والتوقيتات إلى `TIMESTAMPTZ` بعد تدقيق البيانات القديمة وسياسة rounding؛ لم يُنفذ التحويل تلقائياً لتجنب تغيير دلالة البيانات دون قرار.

---

## 7. القرار الحالي

النسخة الحالية اجتازت بوابة البناء والاختبارات الوحدوية وE2E الأساسية، وأُغلقت معظم عيوب `P0/P1` القابلة للحل داخل المستودع دون تغيير التصميم أو الوظائف الأساسية.

القرار المهني الحالي هو **Go إلى staging محصّن** من الناحية البرمجية. أُغلقت لاحقاً قرارات Runtime/token streaming/quota كما هو موثق في الملحق أدناه. يبقى `Production Go` النهائي معلقاً فقط على الإجراءات التشغيلية الخارجية واختبارات السعة والاستعادة الفعلية التي تحتاج بيئة وصلاحيات إنتاج.

---

## 8. ملحق إغلاق القرارات البرمجية — 2026-07-23

هذا الملحق يلغي حالات «يحتاج قرار» السابقة للبنود الثلاثة التالية:

### 8.1 سياسة Runtime toolsets وعزل الشبكة — مكتمل

- أضيف الحقل `runtime_toolsets` لكل Profile مع validation يمنع أسماء Hermes غير المعروفة.
- الوضع الافتراضي الأقل صلاحية هو: `skills`, `vision`, `clarify`, `todo`.
- `web`, `browser`, `terminal`, `file`, `code_execution`, `computer_use`, `delegation` وبقية القدرات لا تُفعّل إلا صراحة في Profile.
- يكتب Runtime `platform_toolsets.cli` ويعطّل جميع toolsets غير المختارة بواسطة `agent.disabled_toolsets`.
- عُزل `hermes-runtime` على شبكة `runtime_net` مستقلة في Production وRelease وE2E؛ لا يشارك شبكة PostgreSQL أو Redis. الـOrchestrator وحده عضو في `app_net` و`runtime_net`.
- لا تزال allowlist لوجهات الإنترنت على مستوى domain/IP مسؤولية firewall أو egress proxy في بيئة النشر؛ Compose يحقق عزل control-plane ولا يستطيع وحده فرض allowlist ديناميكية لمزوّدي LLM.

### 8.2 الحجز الذري للـtoken quota — مكتمل

- أضيف جدول `token_reservations` وترحيل `add_token_reservations`.
- يُحجز قبل inference حد محافظ يشمل:
  - upper bound لحجم input النصي؛
  - `max_tokens_per_request` كاملاً؛
  - مخصصاً ثابتاً لكل مرفق؛
  - overhead محافظاً لأدوات وتعليمات Hermes.
- الحجز ذري على مستوى المستخدم والـProfile ومفتاح المزود، ويحسب الحجوزات المتزامنة غير المنتهية.
- عند النجاح تُسوّى الحصة إلى usage الفعلي مرة واحدة، وعند الفشل أو الإلغاء تُحرر. الحجوزات المنتهية لا تحجب طلبات جديدة.
- أزيل تسجيل usage المكرر من REST وSSE وWebSocket وTelegram وAdmin؛ أصبح `AgentService`/Cowork هو موضع التسوية الوحيد.
- اختبار PostgreSQL متزامن: طلبان يحجز كل منهما 600 من حد 1000؛ نجح واحد فقط، ثم سُجل الاستهلاك الفعلي 300 دون double counting.

### 8.3 Hermes Server token streaming — مكتمل

- استُبدل `hermes --oneshot` لكل تشغيل بـ`hermes serve` على loopback ومنفذ ديناميكي.
- الاتصال داخلي عبر WebSocket JSON-RPC مع session token عشوائي خاص بكل تشغيل.
- تُمرر أحداث `message.delta` فوراً، وتؤخذ النهاية من `message.complete` مع usage الحقيقي.
- أي `approval.request` غير متوقع يُرفض تلقائياً؛ القدرات الخطرة تحتاج أصلاً opt-in في Profile.
- عند timeout أو cancellation تُنهى مجموعة عمليات Hermes ويُنظف الـworkspace المؤقت.
- اختبار فعلي ضد مزود E2E المحلي أعاد ثلاث دفعات مستقلة قبل الاكتمال، مع usage حقيقي ومحتوى نهائي صحيح.

### 8.4 الترحيلات والتحقق النهائي

الرأس النهائي الوحيد للترحيلات:

`add_account_lockout` → `add_profile_runtime_toolsets` → `add_token_reservations`

| الفحص | النتيجة |
|---|---|
| Python compileall | نجح |
| Alembic heads | رأس واحد: `add_token_reservations` |
| Python tests | `14 passed` |
| اختبار token reservation المتزامن على PostgreSQL | نجح |
| اختبار Hermes Server streaming الحقيقي | نجح، 3 chunks وusage فعلي |
| Frontend ESLint | بلا أخطاء؛ تحذير React Hook سابق واحد |
| Frontend production build | نجح |
| Desktop unit tests | `1 passed` |
| Compose config وعزل الشبكة للملفات الثلاثة | نجح |
| Docker E2E من volumes فارغة مع إعادة بناء الصور | `Smoke journey passed` |
| `git diff --check` | نجح |

### 8.5 المتبقي قبل Production Go

المتبقي ليس قراراً برمجياً داخل المستودع:

1. تدوير المفاتيح التي ربما ظهرت تاريخياً، ثم تنفيذ Git history rewrite إن تم اعتماده.
2. توفير registry/digests وCosign/SBOM ومفاتيح توقيع Windows/macOS وupdate feed.
3. توفير مفتاح GPG خارج المضيف وتنفيذ restore drill موثق بقياسات RPO/RTO.
4. تنفيذ load/soak/chaos واختبارات egress الفعلية وفق SLO وعدد المستخدمين وميزانية المزود.
5. فرض allowlist لوجهات المزود عبر firewall أو egress proxy في بيئة staging/production.
