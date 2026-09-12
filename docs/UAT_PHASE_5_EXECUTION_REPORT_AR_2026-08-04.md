# تقرير تنفيذ المرحلة الخامسة — اختبارات الأعطال المقصودة

**التاريخ:** 2026-08-04  
**البيئة:** Docker E2E محلية مماثلة لبيئة on-premises، Dashboard فعلي، وأربع نسخ Desktop packaged ظاهرة ومفتوحة في الوقت نفسه  
**القرار:** **PASS — الانتقال إلى المرحلة السادسة**

## 1. ملخص تنفيذي

نُفذت اختبارات الأعطال المقصودة على المنصة كاملة: FastAPI وHermes Orchestrator وHermes Runtime وPostgreSQL وRedis وWorker وBeat ومزود النموذج وMCP وKnowledge، مع أربع جلسات Desktop مستقلة لموظفي المحاسبة والتسويق والموارد البشرية وتقنية المعلومات.

النتيجة النهائية:

- لا توجد رسالة مفقودة أو مكررة في الحالات المختبرة.
- لم تختلط محادثة أو بيانات مستخدم بمستخدم آخر.
- تعافت جلسات Desktop تلقائياً بعد انقطاع الاتصال وإعادة تشغيل الخدمات.
- لم يظهر spinner دائم أو partial response على أنه جواب مكتمل.
- فشل MCP أو Knowledge أو مزود النموذج بقي محصوراً في المكوّن المتعطل، مع رسالة مفهومة وقدرة على التعافي.
- لم تُفعّل Terminal أو Code Execution ولم يجر أي تغيير في التصميم.
- جميع الخدمات عادت إلى baseline الصحي، ومزود النموذج الحقيقي عاد إلى عنوانه الأصلي.
- سلسلة Audit Log سليمة بعد إصلاح عيب تزامن فعلي اكتُشف أثناء الجولة.

## 2. نطاق التنفيذ الفعلي

| البند | الاختبار الفعلي | النتيجة |
|---|---|---|
| شبكة Desktop | قطع قبل الإرسال، بعد `start`، وبعد `done` | PASS — reconnect تلقائي وexactly-once |
| FastAPI | restart في الخمول، مع 4 WebSockets، وأثناء إنشاء Conversation | PASS |
| Orchestrator | restart أثناء طلب قيد التنفيذ | PASS — retry وتعافٍ دون إعادة تشغيل Desktop |
| Runtime | restart أثناء run منفرد وأربع runs متزامنة | PASS |
| Redis | توقف مؤقت ثم استعادة | PASS — chat العادي استمر والتعافي تم |
| Worker | إنهاء أثناء durable task | PASS — lease recovery على المحاولة الثانية دون تكرار |
| Beat | restart مع scheduled task | PASS — task واحدة فقط |
| PostgreSQL | توقف مؤقت أثناء الطلب | PASS — خطأ واضح، queue آمنة، وتعافٍ exactly-once |
| مزود النموذج | HTTP 500 و429 و401، timeout، malformed SSE | PASS لكل الحالات |
| MCP | outage قبل الطلب، فشل أثناء tool call، approval timeout، replay، وسحب إتاحة إداري | PASS |
| Knowledge | source outage، non-UTF-8، oversized، delete، symlink escape، secret وprompt injection | PASS |
| Audit chain | ضغط إدخالات متزامنة وفحص cryptographic chain | PASS بعد الإصلاح |

## 3. اختبار أربعة مستخدمين حقيقيين

شُغلت أربع نسخ من برنامج Desktop packaged، كل نسخة بمجلد profile وtoken ومستخدم مستقل:

1. Accounting على منفذ debugger `9341`.
2. Marketing على `9342`.
3. HR على `9343`.
4. IT على `9344`.

نُفذت جولة baseline متزامنة ثم أُعيد تشغيل API، ثم أُعيد تشغيله أثناء إنشاء Conversations جديدة، ثم أُوقف Runtime أثناء أربع runs. وصلت الإجابات الصحيحة لكل المستخدمين، وبقي عدد كل رسالة في قاعدة البيانات: user message واحدة وassistant message واحدة.

أبرز نتيجة زمنية في fault overlap كانت نحو 33.2 ثانية لمستخدم Marketing، ضمن حد التعافي المحدد ودون تعليق أو تكرار.

## 4. الأعطال المهمة المكتشفة والإصلاحات

### 4.1 حالة MCP المعروضة كانت قديمة عند تعطل اتصال المدير

**المشكلة:** كان Desktop يستطيع عرض اتصال user على أنه `connected` رغم أن اتصال platform الفعلي أصبح `error`.

**الإصلاح:** أصبحت `/api/mcp/available` تحسب الحالة الفعلية من اتصال platform، كما مُنع user connect في platform mode إذا لم يكن اتصال المدير active وconnected، بما في ذلك خوادم `auth_type=none`.

**التحقق:** عند وضع URL غير صالح ظهر MCP بحالة خطأ، بينما نجحت المحادثة العادية، وبعد إعادة URL الأصلي عاد الخادم سليماً. كما ثُبت سحب binding الإداري أثناء جلسة IT مفتوحة دون التأثير على الجلسة أو بقية المنصة.

### 4.2 حذف Knowledge سليم بصمت عند ظهور ملف غير صالح

**المشكلة:** الملف السابق الصالح كان يمكن أن يُعتبر محذوفاً إذا أصبحت النسخة الحالية non-UTF-8 أو oversized أو symlink خارج الجذر، كما كان `document_count` يحتسب candidates بدلاً من المستندات النشطة فعلياً.

**الإصلاح:** تُسجل الملفات المرفوضة ضمن `seen` للحفاظ على آخر نسخة سليمة، ويُحسب العدد من صفوف `KnowledgeDocument` النشطة. أضيف أيضاً حاجز واضح يعامل Knowledge كبيانات مرجعية غير موثوقة لا كتعليمات.

**التحقق:** بقيت آخر نسخة صالحة متاحة عند source outage والملفات غير الصالحة، وحذف الملف الحقيقي وحده خفّض العدد، ولم يُفهرس symlink خارج الجذر. تم حجب secret وفشل prompt injection في تغيير سلوك Agent.

### 4.3 استجابة Qwen الفارغة

**المشكلة:** بعض الردود كانت تنتهي بلا content صالح بسبب chat template thinking behavior.

**الإصلاح:** تعطيل thinking في OpenAI chat template لهذه البيئة، وإضافة validation يمنع اعتماد استجابة فارغة كجواب ناجح.

**التحقق:** الردود اللاحقة احتوت النص المطلوب، وفشل المزود أصبح خطأً صريحاً قابلاً للاسترداد.

### 4.4 retry وWebSocket في Desktop

**المشكلة:** حالات انقطاع محددة كان يمكن أن تترك queue بلا retry تلقائي كافٍ أو أن تتأخر إعادة WebSocket.

**الإصلاح:** retry متدرج محدود وآمن للـoffline queue، وإعادة اتصال WebSocket، مع idempotency على الخادم وتنظيف failed user messages بصورة scoped.

**التحقق:** القطع بعد `start` وبعد `done` أعاد الاتصال وحفظ الرسالة مرة واحدة بالضبط.

### 4.5 fork في سلسلة Audit Log تحت التزامن

**المشكلة:** trigger القديم كان يحجز advisory lock بعد تخصيص ID، ثم يختار `ORDER BY id DESC`. عند إدخالين متزامنين كان ممكناً أن يُربط ID أصغر بحدث ID أكبر ثم تتفرع السلسلة. اكتُشفت سبع أزواج متضررة في بيانات UAT؛ كل event hash منفرد كان صحيحاً لكن topology لم تكن سلسلة واحدة.

**الإصلاح:** migration جديدة أعادت بناء السلسلة الحالية بترتيب ID، وأصبح trigger يحدد tail الحقيقي الذي لا يملك child بدلاً من أعلى ID. دالة التحقق الجديدة تفحص في آن واحد: self-hash، genesis واحدة، عدم وجود forks، ووصول recursive chain إلى كل الصفوف.

**التحقق المباشر:** بعد الإصلاح أعادت `verify_audit_log_chain()` القيمة `true`. ثم نُفذت 20 عملية admin login متزامنة؛ نجحت كلها HTTP 200 وبقي التحقق `true` بعد ارتفاع السجل إلى 1241 حدثاً. يوجد حدثا `audit_chain_repaired` في قاعدة UAT لأن migration أُعيدت مرة بعد تصحيح نوع `text[]` أثناء تطوير الاختبار؛ هذا خاص ببيئة UAT ولا يعني تكراراً في ترقية إنتاجية واحدة.

## 5. نتائج مزود النموذج

اختُبرت الحالات التالية من خلال fault stub مستقل ثم أُعيد المزود الحقيقي بعد كل حالة:

- HTTP 500.
- HTTP 429.
- malformed SSE.
- timeout.
- invalid API key / HTTP 401.

في كل حالة ظهرت للمستخدم رسالة خطأ واضحة مع reference، لم يبقَ streaming دائماً، بقي الطلب في queue بصورة آمنة، وبعد عودة Qwen أصبحت queue صفراً ووصل marker الصحيح. تحقق فحص DB من وجود user message واحدة وassistant message واحدة لكل marker.

الإعداد النهائي المؤكد:

`OPENAI_BASE_URL=http://host.docker.internal:60000/v1/chat/completions`

ولا توجد عملية تستمع على منفذ fault stub `60010`.

## 6. نتائج MCP وKnowledge

### MCP

- outage لا يسقط chat العادي.
- الحالة الفعلية تصل إلى Desktop ولا تبقى `connected` كاذبة.
- approval timeout يرفض دون استدعاء upstream.
- approval المستعمل لا يقبل replay ويرجع 404.
- فشل upstream أثناء tool call يرجع 502 صريحاً.
- سحب إتاحة MCP من المدير ينعكس أثناء جلسة Desktop المفتوحة.
- خادم Context7 النهائي active على العنوان الأصلي `https://mcp.context7.com/mcp`، بينما binding الذي سُحب في سيناريو IT بقي مسحوباً عمداً كما يقتضي الاختبار.

### Knowledge

- last-good content يبقى عند تعطل share.
- non-UTF-8 وoversized لا يمسحان الوثيقة السليمة السابقة.
- delete الحقيقي يعلّم الوثيقة المحذوفة فقط.
- outside-root symlink لم يُفهرس.
- DLP حجب السر.
- prompt injection داخل الوثيقة لم يغير policy وأعاد Agent marker الآمن مع citation `[K1]`.
- لا توجد Knowledge sources مؤقتة متبقية؛ نتيجة فحص slugs المؤقتة = `0`.

## 7. الاختبارات الآلية النهائية

| المجموعة | النتيجة |
|---|---|
| Python backend/runtime/control-plane | `89 passed` |
| Desktop unit tests | `1 passed` |
| Runtime/MCP targeted suite | `23 passed` |
| JavaScript controller syntax | PASS |
| Python compile للـfault stub وmigration | PASS |
| Docker health | جميع الخدمات المطلوبة تعمل وhealthy حيث يوجد healthcheck |
| Audit chain | `true` |

## 8. أدلة التنفيذ

أهم ملفات الأدلة داخل `uat-evidence/`:

- `api-four-desktops-baseline.jsonl`
- `api-four-desktops-after-restart.jsonl`
- `api-four-desktops-during-conversation-create.jsonl`
- `runtime-four-desktops-midrun.jsonl`
- `resilience-start-live.jsonl`
- `resilience-done-live.jsonl`
- `provider-500-live-failure.jsonl` و`provider-500-live-recovered.jsonl`
- `provider-429-live-failure.jsonl` و`provider-429-live-recovered-real-final.jsonl`
- `provider-malformed-live-failure.jsonl` و`provider-malformed-live-recovered.jsonl`
- `provider-timeout-live-failure.jsonl` و`provider-timeout-live-recovered.jsonl`
- `provider-invalid-key-live-failure.jsonl` و`provider-invalid-key-live-recovered.jsonl`
- `mcp-live-state-effective-outage.jsonl`
- `mcp-live-ordinary-during-outage.jsonl`
- `mcp-live-state-restored.jsonl`
- `mcp-live-admin-revoke.jsonl`
- `live-desktop-uat-final2.jsonl` وفيه إثبات سحب MCP أثناء جلسة IT.
- `knowledge-local-baseline.jsonl`
- `knowledge-local-during-outage.jsonl`
- `knowledge-prompt-injection-live.jsonl`

## 9. قرار بوابة المرحلة

- `S0`: صفر.
- `S1` غير مسترد بعد الإصلاح وإعادة الاختبار: صفر.
- فقد أو تكرار رسائل: صفر في النطاق المنفذ.
- تسرب بين المستخدمين: صفر.
- Terminal/Code Execution: صفر وممنوعة بالسياسة.
- تغييرات التصميم: صفر.

بناءً على ذلك، المرحلة الخامسة **مغلقة بنجاح**، ويُسمح بالانتقال إلى **المرحلة السادسة: انتهاء الجلسة والاستمرار الطويل**.
