# تقرير التنفيذ النهائي لخطة جاهزية المنصة للإنتاج وOn-Premise

**التاريخ:** 2026-08-03  
**النطاق:** FastAPI، Agent Runtime/Hermes، برنامج Desktop، MCP، المهام الخلفية، التدقيق والمراقبة، التقييمات، المعرفة المؤسسية، وحزمة On-Premise  
**المرجع:** `PRODUCTION_SOLUTION_REVIEW_AR_2026-07-16.md` و`ON_PREMISE_COMPETITIVE_GAP_ANALYSIS_AR_2026-08-02.md`

## 1. النتيجة التنفيذية

اكتملت المراحل البرمجية المتفق عليها، مرحلة بعد مرحلة، مع اختبارات آلية واختبارات حية على المنصة وبرنامج Desktop المعبأ. لم تُجر أي تغييرات على التصميم أو الثيم، ولم تُضف Active Directory أو Entra ID أو SSO أو Groups أو أدواراً إضافية. بقي النظام بدوري `admin` و`employee` فقط.

تم تطبيق القرار الأمني الصريح التالي على مستوى الخادم:

> **Terminal وCode Execution ممنوعان بالكامل داخل Agent Runtime.**

الأدوات الفعالة التي ظهرت في الاختبار الحي هي: `skills, vision, clarify, todo`، بينما أرجع الخادم صراحةً `code_execution, terminal` ضمن القائمة المحظورة. لا يستطيع تعديل عميل Desktop أو بيانات Profile إعادة تفعيلهما.

الحالة الحالية من جهة الكود والاختبارات: **جاهز للانتقال إلى Staging محصّن**. الانتقال النهائي إلى Production يبقى مشروطاً فقط بإجراءات تشغيلية لا يمكن تنفيذها من المستودع من دون مفاتيح وصلاحيات المالك، وهي موثقة في القسم 8.

## 2. الضوابط التي تم الالتزام بها

- لم يتغير تصميم Dashboard أو Desktop أو الثيم أو الألوان.
- لم تُحذف أو تُستبدل الوظائف الأساسية الحالية.
- لم تُضف AD/Entra/SSO أو Groups أو RBAC موسع.
- لم تُضف حدود CPU/RAM لكل مستخدم.
- لم يُسمح بـTerminal أو Shell أو Code Execution داخل Runtime.
- استخدمت إضافات محدودة ومباشرة، مع الاعتماد على PostgreSQL وRedis وCelery الموجودين بدلاً من إدخال بنية جديدة غير لازمة.
- حوفظ على مسار `admin/employee` الحالي وعلى تجربة الدخول المستمرة في Desktop باستخدام refresh rotation بدلاً من تسجيل خروج متكرر.

## 3. المراحل المنفذة

### المرحلة 1 — خط الأساس ومنع التنفيذ المباشر

**الحالة: مكتملة ومختبرة.**

- تعريف سياسة Runtime مركزية وحساب policy فعالة من الخادم.
- رفض `terminal` و`code_execution` عند إنشاء Profile أو تعديله، وليس إخفاءهما من الواجهة فقط.
- إرسال policy الفعالة إلى Runtime والتحقق منها قبل التنفيذ.
- تثبيت موافقات الملفات من جهة الخادم؛ قيمة `full_access` القادمة من Desktop لا توسع الصلاحيات.
- الاختبار الحي أظهر:
  - `active_toolsets=skills,vision,clarify,todo`
  - `prohibited=code_execution,terminal`

### المرحلة 2 — الأسرار وحدود الثقة والشبكة

**الحالة: مكتملة ومختبرة.**

- فصل API وHermes Orchestrator وHermes Runtime على حدود شبكة مستقلة.
- API لا يستطيع الوصول مباشرة إلى Runtime في طوبولوجيا Compose الحالية؛ الاتصال يمر عبر Orchestrator.
- Runtime لا يستلم أسرار قاعدة البيانات أو JWT أو Fernet أو SMTP أو Telegram.
- مفتاح مزود النموذج لا يُمرر كسر دائم إلى Runtime؛ يُستخدم token محدود بالـrun عبر model proxy.
- حماية منافذ Runtime بسر مشترك مستقل ومقارنة آمنة.
- الاختبار الحي:
  - الطلب الداخلي بلا سر: `403`.
  - الطلب بالسر الصحيح وصل إلى تحقق payload: `400` المتوقع، ما يثبت نجاح المصادقة الداخلية.
- لكل run مجلد مؤقت منفصل يُحذف تلقائياً؛ نتيجة الفحص بعد الاختبارات: `runtime_temp_dirs=0`.

### المرحلة 3 — عزل API وMCP وحوكمة الموصلات

**الحالة: مكتملة ومختبرة.**

- المدير فقط ينشئ MCP Server ويعدله ويفعله ويحدد Profiles المسموح لها باستخدامه.
- الموظف يرى فقط قائمة MCP التي أتاحها المدير للبروفايل المعيّن إليه.
- لا يستطيع Desktop إرسال تعريف MCP عشوائي أو توسيع allowlist.
- بيانات الاعتماد الحساسة تبقى في Control Plane ولا تُعرض للموظف.
- تنفيذ approval flow لأدوات MCP الحساسة مع ربط الموافقة بالطلب ومنع replay.
- تمرير الأحداث الحية إلى Desktop مع حالات البدء والنجاح والفشل والموافقة.
- تم اختبار MCP حقيقي مع Context7، بما يشمل الظهور للموظف والربط والاستدعاء والموافقة.

### المرحلة 4 — Durable Tasks والجدولة والموافقات

**الحالة: مكتملة ومختبرة.**

- إضافة state machine دائمة للمهام بدلاً من الاعتماد على ذاكرة العملية.
- حالات واضحة للانتظار والتنفيذ والموافقة والنجاح والفشل وdead-letter.
- leases وcheckpoints وidempotency keys لمنع التكرار غير المقصود.
- retry مضبوط مع سجل أحداث لكل انتقال.
- جدولة مهام مع منع تشغيل النسخة نفسها مرتين.
- Approval Inbox بقرار approve/deny مسجل وقابل للتدقيق.
- إصلاح rate limiter حتى لا يعيد تنفيذ الطلب المتغير بعد فشل downstream.
- تخزين Celery beat في مسار مؤقت صالح داخل الحاوية.

### المرحلة 5 — سجل تدقيق مقاوم للعبث وObservability

**الحالة: مكتملة ومختبرة.**

- توسيع Audit Log بحقول actor وsubject وcategory وcorrelation/trace ومعلومات السلسلة.
- سلسلة SHA-256 تربط كل سجل بالسجل السابق.
- دالة قاعدة بيانات `verify_audit_log_chain()` للتحقق الكامل.
- منع `UPDATE` و`DELETE` على Audit Log في PostgreSQL عبر triggers.
- SIEM exporter مع checkpoint وretry وتنقية الحقول الحساسة.
- propagation لـcorrelation ID وtrace ID عبر API ثم Orchestrator ثم Runtime.
- endpoint بصيغة Prometheus على `/api/metrics` دون prompt أو أسرار.
- الاختبارات الحية:
  - تعديل مباشر لسجل التدقيق رُفض من قاعدة البيانات.
  - `fqsaas_audit_chain_valid 1`.
  - لم تظهر أخطاء حديثة في API أو Worker أو Beat أو Orchestrator أو Runtime بعد الاختبار النهائي.

### المرحلة 6 — Agent Evaluations وبوابات الجودة

**الحالة: مكتملة ومختبرة.**

- نماذج وقواعد بيانات لـEvaluation Suite وEvaluation Run وAgent Feedback.
- تقييم deterministic للحالات المتوقعة.
- baseline ومقارنة quality/latency/cost قبل اعتماد التغيير.
- canary decision يعيد `rollback_required` عند كسر الحدود.
- feedback للمستخدم دون تخزين النص الحساس داخل الحقول التحليلية؛ يُحفظ hash عند الحاجة.
- الاختبار الحي شغّل مجموعة من أربع حالات، اجتازت عتبة جودة `0.75` وتم اعتمادها.

### المرحلة 7 — دورة حياة On-Premise

**الحالة البرمجية: مكتملة ومختبرة محلياً.**

- manifest إصدار مع schema compatibility والتحقق من digests.
- تثبيت صور الخدمات الست بصيغة digest: API وAdmin وRuntime وCaddy وPostgreSQL وRedis.
- scripts لبناء حزمة Offline/Air-gapped والتحقق منها وتثبيتها.
- SBOM وحزمة توقيع وإجراء CI لإصدار موقّع.
- upgrade آمن يتضمن:
  - فحص توافق schema.
  - نسخة احتياطية قبل الترقية.
  - migration منفصلة.
  - postflight checks.
  - rollback مشروط عند الفشل.
- النسخة الاحتياطية الإنتاجية المشفرة تشمل قاعدة البيانات وProfiles وAttachments وKnowledge.
- تمرين استعادة فعلي إلى قاعدة بيانات فارغة نجح مع:
  - schema: `knowledge_connectors`.
  - تطابق العدادات: `21|20|56|189|3|3|2` للمصدر والمستعاد.
  - سلامة سلسلة التدقيق: `true`.
  - RTO مقاس: `4` ثوانٍ مقابل هدف `300` ثانية.

### المرحلة 8 — Enterprise Knowledge & Connectors

**الحالة: مكتملة ومختبرة حياً.**

تمت إضافة Knowledge Plane محلية ومناسبة لـOn-Premise من دون تحويل MCP إلى مخزن معرفة:

- نوعا مصدر محدودان ومقصودان:
  - `managed_upload` للمحتوى الذي يديره المدير عبر API.
  - `local_folder` لمجلد SMB/NFS مركب داخل بيئة الشركة.
- المدير ينشئ المصدر ويعدله ويعطله ويحذفه ويحدد الموظفين المسموح لهم مباشرة.
- لا توجد Groups أو صلاحيات إضافية؛ ACL مباشرة بين المصدر والموظف.
- مزامنة دورية كل 15 دقيقة مع retry، ومزامنة يدوية من API.
- incremental sync بالـhash، مع تحديث metadata وحذف المقاطع عند حذف الملف من المصدر.
- منع symlink escape والتحقق من بقاء الملفات تحت الجذور المسموحة.
- أنواع الملفات المدعومة حالياً: `.txt`, `.md`, `.csv`, `.json`.
- حد لحجم الملف وقراءة UTF-8 آمنة.
- DLP قبل الفهرسة لتنقية private keys وAPI keys وكلمات المرور وtokens وأنماط `sk-*`.
- تصنيفان:
  - `internal`.
  - `confidential_local_only` ولا يصل إلى مزود خارجي؛ يُسترجع فقط عندما يكون المزود الفعلي `ollama`.
- PostgreSQL full-text search محلي مع GIN index، من دون خدمة SaaS خارجية.
- citations مستقرة بصيغة `knowledge://source/document#chunk-N`.
- دمج المعرفة تلقائياً في REST chat وSSE وWebSocket/Cowork.
- مقاييس Prometheus لحالة المصادر وعدد الوثائق.
- النسخ الاحتياطي والاستعادة يشملان جداول المعرفة ومجلد المعرفة نفسه.

#### اختبارات Knowledge الحية

- مصدر Managed لموظف مصرح له: نتيجة واحدة؛ موظف غير مصرح له: صفر.
- لم توجد الأسرار التجريبية في المقاطع المخزنة أو نتائج البحث.
- مصدر مجلد محلي وصل إلى `healthy` وفهرس الرمز `NEBULA-2288`.
- مصدر `confidential_local_only` أعاد صفر مع `openai` ونتيجة مع `ollama`.
- حذف وثيقة من المصدر حذف نتائجها من الفهرس.
- تعطيل المصدر أخفى نتائجه فوراً، وإعادة تفعيله أعادها.
- المحادثة الفعلية عبر Hermes أعادت `NEBULA-2288` مع `[K1]` وcitation:
  - `knowledge://live-share-085325/handbook.txt#chunk-0`

## 4. مشكلات ظهرت أثناء الاختبار الحي وتم إصلاحها

### 4.1 استعلام المعرفة الطبيعي كان شديد التقييد

كان البحث المباشر عن الرمز ينجح، لكن سؤالاً كاملاً من المستخدم كان يستخدم `plainto_tsquery` بما يعادل اشتراط وجود جميع كلمات السؤال داخل المقطع نفسه. نتيجة ذلك أن المعرفة لم تصل إلى Runtime رغم وجودها وصحة ACL.

تم الإصلاح بأقل تغيير:

- محاولة exact full-text أولاً.
- عند عدم وجود نتيجة، fallback محدود إلى الكلمات الدلالية بصيغة OR.
- إزالة كلمات السؤال العامة وتفضيل identifiers الرقمية.
- إضافة اختبار regression مستقل.

بعد الإصلاح نجح البحث بالسؤال الطبيعي ونجحت إجابة Hermes مع citation.

### 4.2 اختبار Desktop كان يقبل رسالة الخطأ كنجاح

كان اختبار E2E يعتبر عنصر assistant الفارغ ناجحاً لأن timestamp داخل العنصر غير فارغ. أدى ذلك إلى false positive عند فشل مزود MiniMax التجريبي.

تم إصلاح أداة الاختبار لتقبل فقط محتوى assistant حقيقياً في state، واستخدام `openai` كمسار الاختبار المحلي الافتراضي المعروف في بيئة E2E. أُعيد تشغيل برنامج Desktop المعبأ بعد الإصلاح ونجح الاختبار كاملاً.

هذا التعديل يخص دقة الاختبار فقط ولا يغير واجهة Desktop أو وظائف المستخدم.

## 5. نتائج الاختبارات النهائية

| الاختبار | النتيجة |
|---|---|
| Python compileall | ناجح |
| Alembic head | رأس واحد: `knowledge_connectors` |
| Backend tests | `70 passed` |
| Knowledge tests | `5 passed` |
| `git diff --check` | ناجح؛ لا توجد أخطاء whitespace |
| Frontend ESLint | لا أخطاء؛ تحذير قديم واحد فقط |
| Frontend production build | ناجح؛ 17 صفحة |
| Desktop unit tests | `1 passed` |
| Platform smoke journey | ناجح بالكامل |
| Packaged Desktop E2E | ناجح بالكامل بعد تشديد شرط النجاح |
| Dashboard live HTTP | `200` |
| Runtime auth boundary | `403` بلا سر، ومصادقة صحيحة بالسر |
| Runtime temporary isolation | صفر مجلدات متبقية |
| Audit chain | صحيحة |
| Restore drill | ناجح، RTO = 4 ثوانٍ |
| Recent service error scan | صفر أخطاء بعد الجولة النهائية |

رحلة Desktop النهائية تحققت من:

- تفعيل الحساب في التطبيق المعبأ.
- WebSocket chat مع محتوى مساعد حقيقي.
- فحص مساحة العمل والسياق والقراءة والمعاينة وتطبيق تغيير ملف بموافقة.
- Telegram binding.
- offline queue.
- حالة تحديث التطبيق.

رحلة Smoke تحققت من:

- دخول المدير.
- إعداد pricing ومفتاح مزود مشفر.
- إنشاء Profile وموظف وتعيينهما.
- تفعيل الموظف.
- محادثة حقيقية عبر Hermes.
- WebSocket ticket.
- run events وsessions.
- KPIs وusage reporting والتنبيهات.

## 6. الملفات والمكونات الرئيسية المضافة

### السياسة والأمان

- `app/core/runtime_policy.py`
- `app/hermes_orchestrator_app.py`
- `app/local_hermes_runtime_app.py`
- `tests/test_orchestrator_security.py`
- `tests/test_runtime_toolsets.py`

### المهام الدائمة

- `app/models/durable_task.py`
- `app/services/durable_task_service.py`
- `app/api/durable_tasks.py`
- `app/schemas/durable_task.py`
- `tests/test_durable_tasks.py`

### التدقيق والمراقبة

- `app/core/audit_context.py`
- `app/api/observability.py`
- `app/services/audit_service.py`
- `tests/test_audit_observability.py`

### التقييمات

- `app/models/evaluation.py`
- `app/services/evaluation_service.py`
- `app/api/evaluations.py`
- `tests/test_evaluation_gates.py`

### المعرفة المؤسسية

- `app/models/knowledge.py`
- `app/services/knowledge_service.py`
- `app/api/knowledge.py`
- `app/schemas/knowledge.py`
- `tests/test_knowledge_connectors.py`

### On-Premise والإصدار

- `scripts/build_release_manifest.py`
- `scripts/verify_release_bundle.py`
- `deploy/build_offline_bundle.sh`
- `deploy/install_offline.sh`
- `deploy/upgrade.sh`
- `deploy/restore_drill.ps1`
- `.github/workflows/signed-release.yml`

### الترحيلات

- `prohibit_runtime_execution_toolsets`
- `allow_multiple_pending_telegram_bindings`
- `add_durable_tasks`
- `add_tamper_evident_audit`
- `add_evaluation_gates`
- `add_knowledge_connectors`

## 7. ملاحظة إصدار Desktop

فحص `desktop release:check` فشل مغلقاً كما هو مصمم، للأسباب التالية فقط:

- `UPDATE_FEED_URL` غير مضبوط.
- متغيرات Windows code signing غير موجودة.
- API URL الخاص بالإصدار ما زال يشير إلى localhost.

هذه ليست أخطاء بناء؛ اختبار Desktop وبناء المنصة نجحا. لا يجب تجاوز هذه البوابة بخيار insecure. يجب إدخال قيم الإنتاج الحقيقية في CI/بيئة الإصدار.

## 8. الإجراءات الخارجية المتبقية قبل Production Go

هذه البنود ليست كوداً ناقصاً، ولا يمكن إتمامها بأمان من دون صلاحيات المالك أو بنية العميل:

1. تدوير أي مفاتيح ظهرت تاريخياً والتأكد من إبطالها لدى المزودين.
2. تنفيذ Git history rewrite بالتنسيق مع جميع مستخدمي المستودع، ثم تشغيل secret scan على التاريخ المنظف.
3. توفير مفاتيح Cosign/GPG ومفاتيح Windows/macOS code signing داخل secret store الخاص بالـCI.
4. ضبط Registry الإنتاجي ودفع الصور الست الموقعة فعلياً، ثم تثبيت digests الناتجة في manifest النهائي.
5. ضبط `UPDATE_FEED_URL` وAPI URL وDNS/TLS وشهادات العميل الفعلية.
6. تشغيل load test وفق حجم الشركة المتوقع داخل بنيتها، لأن النتائج تعتمد على العتاد ومزود النموذج.
7. تنفيذ failover/HA وrestore drill في بيئة العميل الفعلية، مع تخزين النسخ خارج الخادم وقياس RPO/RTO المتفق عليه.
8. اعتماد سياسة retention للـaudit والنسخ الاحتياطية ومتطلبات SIEM الخاصة بكل شركة.

## 9. ما لم يُنفذ عمداً

- Active Directory أو Entra ID.
- OIDC/SAML SSO.
- Groups أو RBAC أوسع من `admin/employee`.
- حدود CPU/RAM لكل مستخدم.
- Terminal أو Shell أو Code Execution.
- أي إعادة تصميم للـDashboard أو Desktop.

## 10. القرار النهائي

من جهة التنفيذ داخل المستودع والاختبارات المحلية الحية:

> **المراحل المتفق عليها مكتملة، والمنصة مؤهلة لـStaging محصّن.**

قرار Production Go يصبح مناسباً بعد إغلاق البنود التشغيلية في القسم 8، خصوصاً تدوير الأسرار وتنظيف تاريخ Git والتوقيع الحقيقي واختبارات load/failover داخل بيئة العميل. لا توجد توصية بتغيير التصميم أو توسيع نظام الأدوار أو إعادة هندسة المنصة.
