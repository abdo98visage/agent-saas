# تحليل فجوات المنصة On‑Premise مقارنةً بـ Claude Cowork وChatGPT Codex

> **نوع الوثيقة:** مراجعة منتج وهندسة حلول للإنتاج — لا تتضمن تعديلات برمجية  
> **تاريخ التقييم:** 2026-08-02  
> **نطاق القرار:** نسخة مستقلة من المنصة تُنشر داخل بيئة كل شركة (Single-Customer On‑Premise Deployment)  
> **المرجع الداخلي:** حالة المستودع والكود الفعلي في تاريخ التقييم، لا الوصف التسويقي ولا وثائق قديمة منفردة

---

## 1. الخلاصة التنفيذية

المنصة الحالية **ليست مجرد واجهة Chat**. لديها قاعدة جيدة ومتماسكة تشمل:

- تطبيق Desktop يصل إلى الملفات المحلية ضمن Workspace محدد، ويستطيع قراءة الملفات والبحث فيها وتطبيق تعديلات ذرية مع فحص مسبق وrollback.
- FastAPI control plane مع مستخدمين، Profiles، Skills، Assignments، جلسات، مرفقات، مفاتيح مزودين، حصص، تكلفة، KPIs وAudit Log.
- Hermes Agent Runtime مستقل، toolsets محكومة لكل Profile، approvals، حجز ذري للـtoken quota، وtoken streaming حقيقي.
- MCP control plane حديث: المدير يضيف الخوادم المعتمدة ويربطها بالـProfiles ويحدد الأدوات والموافقات، والموظف لا يستطيع إضافة MCP عشوائي من خارج الكتالوج.
- نشر Docker محصّن نسبياً، شبكات منفصلة، containers غير root، readiness، migrations، Redis/Celery، ونسخ احتياطي/استعادة برمجية.

لكن عند تقييمها كمنتج يُباع لشركات ويُركّب داخل شبكتها، فإن الفجوة الأساسية ليست في “ذكاء الوكيل”، بل في **الغلاف المؤسسي الذي يجعل الوكيل قابلاً للحوكمة والتشغيل والدعم على نطاق شركة كاملة**.

القرار المهني هو:

> **المنصة جاهزة كأساس قوي لـControlled On‑Premise Agent Platform، لكنها ليست بعد Enterprise On‑Premise Product مكتمل دورة الحياة.**

أهم ما يجب إضافته، بالترتيب، هو:

1. هوية مؤسسية: OIDC/SAML، Active Directory/LDAP، SCIM/JIT، مجموعات وRBAC دقيق.
2. سياسة مركزية إلزامية تصل إلى Desktop وRuntime وتفشل بشكل مغلق عند غيابها.
3. عزل تنفيذي مستقل لكل Run/Task، بدلاً من الاكتفاء بحاوية Runtime محصّنة مشتركة.
4. طبقة Enterprise Knowledge & Connectors تحافظ على صلاحيات المصدر، والفهرسة، والمراجع، والحذف.
5. Durable Tasks: مهام طويلة ومجدولة وقابلة للاستئناف بعد إعادة التشغيل.
6. Audit/Compliance/Data Governance قابلة للتصدير إلى SIEM، مع retention وlegal hold وDLP.
7. حزمة تشغيل On‑Premise حقيقية: HA، air-gap، private registry، upgrade/rollback، DR وقياس RPO/RTO.
8. Observability & Evaluation: traces لكل Run، metrics، quality regression، وتقييم قبل ترقية Profile أو model.

أما الميزات مثل التحكم العام بالكمبيوتر، الهاتف، الذاكرة الشخصية العامة، ومتجر Plugins مفتوح فلا ينبغي أن تسبق هذه البنود. بعضها مفيد، لكنه ليس شرطاً أولياً، وبعضه يرفع المخاطر في بيئات الشركات.

---

## 2. منهجية التقييم وحدوده

### 2.1 ما الذي تم فحصه داخل المنصة؟

شمل الفحص طبقات الحل الثلاث وما حولها:

- **Backend/API:** المسارات، المصادقة، الجلسات، Chat/Streaming/WebSocket، الإدارة، الحصص، المرفقات، MCP وTelegram.
- **Agent Runtime:** Orchestrator، تشغيل Hermes، toolsets، approvals، streaming، cancellation، timeouts، وعزل الشبكات.
- **Desktop:** إدارة الجلسة، حفظ أسرار الدخول، local workspace، offline queue، preview/apply للتغييرات، updater وعقد الاتصال.
- **Dashboard:** الموظفون، Profiles، Skills، Assignments، MCP، الجلسات، KPIs، Usage، Audit، وحالة Hermes.
- **البيانات:** SQLAlchemy models، Alembic migrations، PostgreSQL، Redis، token reservations وAgent events.
- **التشغيل:** ملفات Compose للإنتاج والإصدار، container hardening، CI، backup/restore، وإجراءات الإصدار.
- **التوثيق الداخلي:** مراجعة الإنتاج السابقة، تقرير remediation، معمارية المنصة وتقارير E2E.

### 2.2 ما المقصود بالمقارنة؟

المقارنة ليست لإعادة بناء Claude أو Codex حرفياً. المنتجين مختلفان:

- **Claude Cowork** موجّه بصورة أكبر لأعمال المعرفة: ملفات، مستندات، جداول، عروض، تطبيقات، connectors، plugins ومهام متكررة.
- **ChatGPT Codex** أقوى في دورة العمل البرمجية: repository، terminal، Git، worktrees، review، sandbox، automation وواجهات برمجية.
- **المنصة الحالية** هجينة: موظف رقمي مؤسسي عام، مع Desktop محلي وHermes Runtime مركزي وإدارة On‑Premise.

لذلك أُخذت فقط القدرات التي تضيف قيمة مباشرة أو تقلل مخاطرة حقيقية في نشر داخل شركة.

### 2.3 درجات الحالة المستخدمة

| الحالة | المعنى |
|---|---|
| **موجود** | يوجد مسار متكامل قابل للاستخدام والإدارة، وليس مجرد حقل أو اسم toolset. |
| **جزئي** | توجد بنية جيدة، لكن تنقصها الحوكمة أو دورة الحياة أو تجربة الإدارة. |
| **غير موجود** | لم يظهر في الكود أو التشغيل مسار منتج متكامل لهذه القدرة. |
| **مشروط** | لا يلزم لكل عميل، ويُفعّل فقط حسب القطاع والمخاطر. |

> ظهور اسم مثل `computer_use` أو `memory` ضمن toolsets لا يعني أن هناك منتجاً متكاملاً له. وكذلك وجود Celery لا يعني وجود user-facing durable tasks، ووجود Audit table لا يعني Compliance-grade audit.

---

## 3. صورة المنصة الحالية كما هي فعلاً

### 3.1 نقاط القوة الحالية

#### أ. Control plane واضح

يوجد فصل جيد بين صلاحية المدير وتجربة الموظف. المدير يدير الموظفين والبروفايلات والمهارات والمفاتيح والحصص والتكلفة والتعيينات، ويراقب النشاط والجلسات وحالة Runtime.

#### ب. سياسة Runtime أفضل من كثير من النماذج الأولية

الـProfile لا يحدد prompt فقط؛ بل يملك مزوداً وحدوداً وtoolsets وallowed tools وأدوات تحتاج approval وMCP bindings. كما أن الحصة تُحجز قبل inference ثم تُسوّى على الاستهلاك الفعلي، ما يقلل السباق والتجاوزات المتزامنة.

#### ج. MCP مُصمم بالطريقة الصحيحة للموظف المؤسسي

الموظف لا يُدخل أي MCP URL من رأسه. المدير ينشئ كتالوجاً معتمداً، يجري discovery، يربط الخادم بالـProfile، ويحدد allowlist للأدوات وما يحتاج موافقة. ثم يستطيع الموظف فقط الاتصال بما أتيح له. هذه نقطة قوة ينبغي البناء فوقها، لا استبدالها بتمرير إعدادات MCP خام إلى Hermes.

#### د. Desktop يملك mediation محلياً مفيداً

الوصول للملفات ليس وصولاً عشوائياً لكل الجهاز. توجد فكرة Workspace، containment لمسارات الملفات، قراءة وبحث، preview قبل الكتابة، preconditions، كتابة ذرية وrollback. هذا أساس مهم لنسخة On‑Premise.

#### هـ. عناية إنتاجية موجودة بالفعل

هناك migrations، readiness، refresh sessions، WS tickets، حماية للمرفقات، idempotency، timeouts، stale-run cleanup، Redis presence، CI، container hardening، backup/restore، وإرشادات release/signing. هذه ليست تفاصيل تجميلية؛ هي أساس صالح للتطور.

### 3.2 الحدود الحالية المهمة

- الهوية محلية بدورين رئيسيين `admin` و`employee`، ولا يوجد مسار مؤسسي كامل لـSSO/SCIM/LDAP/groups/custom roles.
- النشر مستقل لكل شركة، لكنه لا يملك بعد **deployment identity/config bundle/license/lifecycle plane** واضحاً.
- Runtime محصّن كخدمة، لكن لا توجد دلالة واضحة على sandbox/container/VM مستقل لكل Run مع سياسة موارد وشبكة وأسرار مؤقتة.
- Sessions وتجربة العمل تتمحور حول المحادثة، وليس حول Task دائم له state machine وcheckpoint وretry schedule.
- MCP ممتاز كـtool transport/control plane، لكنه ليس بحد ذاته enterprise knowledge ingestion أو search index أو ACL-aware retrieval.
- Audit وKPIs موجودان، لكن لا توجد طبقة تصدير مستمرة وموثوقة إلى SIEM ولا retention/legal hold/DLP كاملة.
- Desktop يتعامل مع الملفات، لكنه غير Git-aware مثل Codex: لا worktrees أو branch lifecycle أو diff/review/stage/commit كمسار منتج متكامل.
- Skills موجودة كتعريفات ومزامنة، لكن ليست بعد supply chain مؤسسية موقعة، versioned، قابلة للترقية والرجوع والنشر المرحلي.
- Compose جيد لنشر واحد، لكنه لا يحقق وحده HA، zero/low-downtime upgrade، air-gapped delivery، أو DR drill موثق.
- Sentry اختياري وبعض monitoring موجود، لكن لا يوجد end-to-end trace موحد لكل agent step/tool/approval/model call ولا quality evaluation gate.

---

## 4. ما الذي يميز المنافسين فعلاً؟

## 4.1 Claude Cowork

بحسب وثائق Anthropic الرسمية الحالية، Cowork يقدم نموذج “تفويض إلى نتيجة” لأعمال المعرفة، مع:

- عمل متعدد الخطوات على ملفات ومجلدات وتطبيقات المستخدم، وإنتاج مستندات وجداول وعروض وتقارير.
- جلسات remote معزولة، مع بقاء local execution في بعض desktop deployments، وسياسات منفصلة للمجلدات والشبكة والأدوات.
- scheduled tasks تعمل دورياً أو عند الطلب، ولها سجل تشغيل ويمكن إيقافها واستئنافها وتعديلها.
- plugins تجمع skills وconnectors وsub-agents في حزمة واحدة، مع marketplace تنظيمي وسياسات required/available/not available.
- custom connectors عبر remote MCP، مع إدارة على مستوى المنظمة واتصال المستخدم بحسابه الخاص.
- مشاريع تحتوي ملفات وروابط وتعليمات وذاكرة مرتبطة بالمشروع.
- computer use للتعامل مع التطبيقات عند السماح به.
- موافقات للأدوات، وإمكانية منع “always allow” للأدوات ذات الأثر، وسياسة “الأكثر تقييداً هو الفائز”.
- تحكم Enterprise عبر groups/custom roles وبعض مفاتيح MDM، وسياسات network egress، trusted-device requirements وrecent sign-in للجلسات البعيدة.
- تصدير أحداث Cowork عبر OpenTelemetry إلى أدوات المراقبة وSIEM.

لكن توجد حدود يجب عدم تجاهلها:

- Cowork نفسه ما زال beta على بعض الأسطح.
- وثائق Anthropic تصرح أن نشاط Cowork لا يظهر حالياً في audit logs/Compliance API، وأن المحادثات المحلية لا تُدار أو تُصدّر مركزياً من الإدارة.
- عزل VM يقلل رؤية EDR داخل البيئة؛ Anthropic نفسها تذكر هذه المفاضلة.
- كثير من remote connectors تمر عبر سحابة Anthropic وليست مناسبة كما هي لبيئة air-gapped.

إذن Cowork مرجع قوي لتجربة العمل والمهام والحزم، لكنه ليس قالباً حرفياً للحوكمة On‑Premise.

## 4.2 ChatGPT Codex

بحسب الدليل الرسمي الحالي لـCodex، أهم القدرات ذات الصلة هي:

- sandbox وapproval policy منفصلان: ما يسمح به النظام تقنياً، ومتى يجب سؤال المستخدم.
- network disabled افتراضياً في أوضاع محلية، مع سياسات وجهات allow/deny وإدارة مركزية للمتطلبات.
- Git-aware projects: diff، inline comments، stage/revert، commit، push وpull request.
- worktrees لعزل الأعمال المتوازية عن checkout الأساسي.
- integrated terminal مربوط بالمشروع أو worktree، ويستطيع الوكيل قراءة ناتجه للتحقق.
- code review على branch/commit/uncommitted changes مع findings مرتبة وبدون تعديل تلقائي للشجرة.
- long-running goals قابلة للتوجيه والإيقاف والاستئناف، وscheduled tasks ببيئة تنفيذ محددة.
- remote connections لمتابعة العمل والموافقات والنتائج من جهاز آخر، مع الاحتفاظ ببيئة وأذونات الجهاز المضيف.
- plugins وskills وMCP وhooks، مع قيود إدارية على المصادر والخوادم والسياسات.
- SDK، App Server، non-interactive mode وGitHub Action للاستخدام البرمجي وCI.
- managed configuration تُفرض على Desktop/CLI/IDE، مع requirements لا يستطيع المستخدم تجاوزها وfail-closed عند غياب bundle موثوق.
- groups/SCIM/RBAC، analytics وCompliance API لفصل تقارير التبني عن سجلات التحقيق والتدقيق.

Codex مرجع قوي للعزل، التحقق، Git workflow، السياسات المحلية والواجهات البرمجية. لكنه منتج coding-first، لذلك لا يلزم نسخ كل عناصره إلى منصة موظفين رقميين عامة.

---

## 5. مصفوفة المقارنة

| القدرة | المنصة الحالية | Claude Cowork | ChatGPT Codex | الحكم للمنصة |
|---|---|---|---|---|
| ملفات محلية ضمن نطاق محدد | **موجود** مع containment وatomic apply | **موجود** مع folder-scoped access | **موجود** ضمن project/workspace | حافظ على الأساس وعمّق الحوكمة |
| MCP مع تحكم المدير | **موجود حديثاً**: catalog + profile binding + tool policies | custom connectors وMCP + org controls | MCP + managed allowlists | المنصة في اتجاه صحيح جداً |
| مهارات/حزم قابلة للتوزيع | **جزئي**: Skills وProfiles | Plugins تجمع skills/connectors/sub-agents + marketplace | Skills/Plugins/Hooks + admin controls | يلزم registry/versioning/signing |
| مهام طويلة قابلة للاستئناف | **جزئي**: Run/Events وtimeouts؛ لا durable user task lifecycle كامل | أهداف متعددة الخطوات وجلسات remote | Goal/long-running work | **فجوة حرجة** |
| مهام مجدولة للمستخدم | **غير موجودة كمنتج**؛ Celery للصيانة | Scheduled tasks كاملة | Scheduled tasks | **فجوة حرجة** |
| عزل لكل تشغيل | **جزئي**: runtime container محصّن وشبكة منفصلة | isolated remote environment أو local VM | cloud containers/OS sandbox/worktree | **فجوة حرجة** |
| سياسة موافقات وأدوات | **موجود جزئياً بقوة** على Profile/MCP | tool approvals وقيود org/role | sandbox + approvals + auto review + requirements | أضف policy distribution وdecision trace |
| سياسة شبكة دقيقة | **جزئي**: فصل شبكات؛ egress allowlist خارجي | org network/egress controls | allow/deny destination policy | **P0 للنشر الحساس** |
| هوية مؤسسية | **غير موجودة**: local login/invite | SSO/JIT/SCIM/groups/custom roles | workspace SSO/SCIM/groups/RBAC | **فجوة بيع واعتماد P0** |
| إدارة Desktop/الجهاز | **جزئي**: signing/updater scaffolding | MDM keys وtrusted-device controls | managed config وWindows MDM deployment | **فجوة P0** |
| معرفة مؤسسية مفهرسة بصلاحيات | **غير موجودة كطبقة مستقلة**؛ MCP ينفذ الأدوات | connectors/plugins ومصادر عمل | plugins/apps/connectors/MCP | **فجوة P0/P1 حسب use case** |
| Git/worktree/review | **غير موجود كمسار منتج** | ليس محور Cowork | قوي ومتكامل | **P1** للبروفايلات التقنية فقط |
| إنشاء artifacts مكتبية | **يعتمد على Runtime/Skill وليس surface محكومة** | قدرة أساسية للمستندات والجداول والعروض | متاح عبر Work/plugins | **P1** للموظف المعرفي |
| Computer Use | اسم toolset موجود، لكن ليس منتجاً مثبتاً end-to-end | موجود ومصرح به | موجود مع sandbox/approvals | **P2 مشروط** وعالي المخاطر |
| تعاون ومشاركة وهandoff | **جزئي**؛ جلسات مستخدم وقنوات مختلفة | projects؛ session sharing محدود حالياً؛ Dispatch لبعض الخطط | projects/remote/handoff ومتابعة | **P1** |
| Audit/Compliance export | **جزئي**: DB audit + activity/KPI | OTEL لـCowork؛ Claude Enterprise audit/Compliance مع استثناءات Cowork | Compliance API + analytics | **فجوة P0** |
| Observability لكل خطوة | **جزئي**: logs/events/alerts/Sentry اختياري | OTEL لأحداث الأدوات والملفات والموافقات | logs/analytics/hooks/telemetry | **فجوة P0/P1** |
| Evaluations/regression | **غير ظاهر كمنظومة منتج** | ليست أهم ميزة ظاهرة في Cowork | review/validation workflows؛ يمكن دمجه برمجياً | **فجوة حرجة للجودة** |
| API/SDK/CLI/CI مستقرة | FastAPI داخلي، لا public automation contract واضح | connectors/plugins؛ ليس runner عاماً | SDK/App Server/non-interactive/GitHub Action | **P1** |
| HA/Air-gap/upgrade/DR | **جزئي**: Compose + backup/restore scripts | خدمة سحابية؛ ليست مرجع On‑Prem | خدمة/عميل سحابي؛ ليست مرجع On‑Prem | هنا يجب أن تتفوق المنصة |
| حصص وتكلفة حسب مستخدم/Profile | **موجود بقوة** | spend controls واستهلاك Enterprise | usage/spend analytics | حافظ عليها ووسعها للمجموعة والقسم |

---

## 6. الفجوات الحرجة التي يجب إضافتها

## P0-1 — الهوية المؤسسية وإدارة دورة حياة المستخدم

### لماذا هي حرجة؟

أول سؤال من بنك أو جهة حكومية أو شركة كبيرة لن يكون “هل يدعم MCP؟”، بل:

- هل يدخل الموظف بحساب الشركة؟
- هل يُسحب وصوله فور تعطيله في Active Directory؟
- هل يمكن إعطاء قسم المالية أدوات تختلف عن قسم التطوير؟
- هل يمكن فرض MFA وسياسة جلسة وIP allowlist؟
- من يستطيع رؤية المحادثات أو تعديل Profiles أو إدارة connectors؟

الدوران الحاليان `admin/employee` لا يكفيان. كما أن invitation lifecycle منفصل عن HR/IdP يؤدي إلى حسابات يتيمة وتأخير في الإلغاء.

### الموجود حالياً

- Local email/password، activation/invite، access/refresh sessions، lockout.
- صلاحية إدارية عامة وفصل بيانات المستخدم بواسطة `user_id`.
- Department وProfile assignments.

### الحد الأدنى الصحيح المطلوب

1. OIDC أولاً، ثم SAML 2.0 عند حاجة العملاء؛ لا يلزم بناء IdP.
2. تكامل Active Directory/Entra ID/Keycloak/Okta عبر معيار، وليس provider-specific hacks.
3. JIT provisioning وخيار SCIM 2.0 للمزامنة والإلغاء والمجموعات.
4. Groups من مصدر موثوق وربط المجموعة بـProfiles، MCP servers، models، quotas وcapabilities.
5. RBAC بقدرات مستقلة، مثل:
   - Platform Owner
   - Security Admin
   - Identity Admin
   - Agent/Profile Admin
   - Connector Admin
   - Auditor/Read-only
   - Employee
6. Service accounts لعمليات CI والتكامل، مع scopes وانتهاء وتدوير.
7. MFA/step-up auth للعمليات الحساسة، session lifetime، device/session revocation.
8. Emergency local admin “break glass” مع حفظ سري خارج الخدمة وتدقيق صارم.

### معيار القبول

- تعطيل مستخدم في IdP يمنع access token الجديد ويلغي الجلسات ضمن زمن معلوم ومختبر.
- group membership changes تغيّر القدرات تلقائياً ولا تعتمد على تعديل يدوي.
- لا يستطيع أي role إدارة مجال خارج صلاحياته.
- يوجد تقرير يوضح effective permissions للمستخدم ولماذا مُنحت.
- يعمل تسجيل الدخول في بيئة لا تحتوي اتصالاً بالإنترنت الخارجي عند استخدام IdP داخلي.

---

## P0-2 — Policy Plane مركزية وملزمة للـDesktop والـRuntime

### لماذا هي حرجة؟

سياسة الـProfile الحالية جيدة، لكنها تترك أسئلة مؤسسية:

- ماذا لو كان Desktop قديماً ولا يفهم policy جديدة؟
- ماذا لو تعذر جلب السياسة؟ هل يبدأ بأذونات أوسع؟
- من يمنع المستخدم من تشغيل local MCP أو تغيير API endpoint أو updater channel؟
- كيف تُفرض certificate authority داخلية وproxy وnetwork destinations؟
- كيف يعرف فريق الأمن السياسة الفعلية التي طُبقت على Run معين؟

Codex يميز بوضوح بين managed defaults وadmin-enforced requirements، وCowork يقدم org/device controls. هذا النمط مطلوب محلياً.

### الحد الأدنى الصحيح المطلوب

1. Policy bundle موقعة وversioned صادرة من Dashboard/Control Plane.
2. precedence معلن: platform hard limits ← company policy ← group policy ← profile policy ← user preference.
3. **Most restrictive wins** في الأدوات والشبكة والموافقات، إلا عند وجود استثناء إداري موثق.
4. fail-closed للقدرات الحساسة إذا كانت السياسة مفقودة أو منتهية أو غير متوافقة.
5. سياسات تشمل:
   - allowed/required Desktop versions
   - API endpoint وTLS trust
   - local folder scope
   - MCP identities المسموحة
   - toolsets وapproval modes
   - egress destinations
   - attachment types/sizes
   - clipboard/screenshot/computer-use
   - local retention/offline queue
   - telemetry destinations
6. نشر عبر MDM/GPO/registry/plist أو ملف system-level محمي، مع cloud/control-plane delivery كمسار ثانٍ.
7. policy simulator في Dashboard يشرح effective policy قبل النشر.

### معيار القبول

- تعديل policy لمجموعة يصل إلى الأجهزة ويظهر رقم نسخته.
- جهاز لا يستطيع التحقق من توقيع السياسة لا يشغّل capability حساسة.
- لا يستطيع employee تجاوز policy بتعديل ملف محلي أو request payload.
- كل Agent Run يسجل policy version وprofile version وclient version.

---

## P0-3 — عزل تنفيذي مستقل لكل Run/Task

### لماذا هي حرجة؟

container hardening للخدمة مهم، لكنه لا يساوي عزل تشغيل عن تشغيل. عند خدمة عدة موظفين على Runtime واحد، يجب منع:

- بقايا ملفات أو environment من Run سابق.
- تأثير عملية runaway في بقية المستخدمين.
- مشاركة credentials أو sockets أو cache بدون قصد.
- خروج أداة إلى شبكة داخلية أوسع من المطلوب.
- تضارب مهام متوازية على workspace واحد.

Cowork يستخدم بيئات معزولة/VM محلية، وCodex يستخدم OS sandbox أو containers وworktrees. المنصة تحتاج نموذجها الملائم On‑Premise.

### الحد الأدنى الصحيح المطلوب

1. Run sandbox مؤقت لكل Task:
   - container مستقل أو sandbox process قوي؛
   - filesystem مؤقت؛
   - mount للمدخلات المطلوبة فقط؛
   - UID/namespace مستقل؛
   - CPU/RAM/PID/time limits.
2. Network policy لكل Run/Profile، لا مجرد شبكة Compose مشتركة.
3. secrets broker يحقن credential قصير العمر للأداة المطلوبة فقط، ولا يكتب السر داخل prompt أو disk.
4. workspace snapshot/checkpoint وcleanup مؤكد بعد النجاح والفشل والإلغاء.
5. لا تشغيل terminal/code execution على host مباشرة.
6. فصل agent loop عن execution sandbox حتى يبقى التحكم والإلغاء والمراقبة متاحاً عند تعطل sandbox.
7. مسار quarantine للأعمال المشتبه بها، وسجل لكل process/tool/network decision.

### لا نحتاجه الآن

لا يلزم البدء بـmicroVM معقدة لكل طلب. Container per-run مع seccomp/AppArmor/SELinux، filesystem وegress مضبوطين، قد يكون الحد الأدنى المناسب. تستخدم VM فقط للعملاء الذين تتطلب مخاطرهم ذلك.

### معيار القبول

- اختبار cross-run leakage لا يستطيع رؤية ملف أو env أو token من Run آخر.
- fork bomb أو استهلاك ذاكرة لا يسقط الخدمة ولا يؤثر في Run مجاور.
- egress إلى وجهة غير مسموحة يُمنع تقنياً ويسجل.
- cancellation يوقف شجرة العمليات ويزيل workspace والأسرار.
- نتائج اختبارات escape والعزل جزء من release gate.

---

## P0-4 — Enterprise Knowledge & Connectors، وليس MCP فقط

### الفرق المهم

MCP يجيب عن: **كيف يكتشف الوكيل أداة ويناديها؟**  
لكنه لا يجيب وحده عن:

- كيف نزامن ملايين المستندات؟
- كيف نحافظ على ACL لكل ملف؟
- كيف نحذف المعلومة من الفهرس عند حذفها من المصدر؟
- كيف نعرض citation واضحاً للمستخدم؟
- كيف نمنع HR agent من استرجاع مستند قانوني لا يحق للموظف قراءته؟
- كيف نتعامل مع freshness، versions، duplicates وPII؟

المنصة لديها MCP control plane جيد، ويجب إبقاؤه طبقة تنفيذ. فوقه تحتاج Knowledge plane.

### الحد الأدنى الصحيح المطلوب

1. Connector catalog مع نوعين واضحين:
   - **Action connectors/MCP** لتنفيذ الأفعال.
   - **Knowledge connectors** للفهرسة والاسترجاع.
2. موصلات أولية حسب السوق المستهدف، لا عشرات الموصلات العشوائية. غالباً:
   - SharePoint/OneDrive أو Google Drive
   - Confluence
   - GitHub/GitLab
   - ملفات شبكة SMB/NFS
   - قاعدة بيانات read-only محددة
3. incremental sync + delete propagation + retry/dead-letter.
4. ACL-aware retrieval: المستخدم لا يسترجع إلا ما يستطيع الوصول إليه في المصدر.
5. hybrid search، metadata filters، citations وروابط للمصدر/version.
6. سياسة freshness وindex health ودعم إعادة الفهرسة.
7. classification/redaction ومنع إدخال secrets أو أنواع بيانات محظورة إلى model غير مسموح.
8. اختيار storage محلي: PostgreSQL/pgvector كبداية أو محرك بحث معتمد عند الحجم، دون إدخال بنية موزعة بلا حاجة.
9. admin dashboard لصحة sync، عدد الوثائق، الأخطاء، آخر مزامنة، ومسح المصدر.

### معيار القبول

- تغيير ACL في المصدر ينعكس في retrieval ضمن SLA محدد.
- حذف الملف يحذفه من الفهرس والcache والنتائج.
- كل إجابة معرفية تعرض citations قابلة للفتح وهوية المصدر وتاريخه.
- اختبارات permission leakage تشمل مستخدمين ومجموعات مختلفة.
- يستطيع العميل تشغيل كامل pipeline داخل شبكته دون خدمة فهرسة خارجية إلزامية.

---

## P0-5 — Durable Tasks والمهام المجدولة

### لماذا هي حرجة؟

القيمة الحقيقية لوكيل مؤسسي ليست فقط الرد على prompt، بل تولي عملية:

- تقرير صباحي من عدة أنظمة.
- مراجعة ملفات دورية.
- تلخيص Tickets وإعداد مسودات.
- مراقبة حدث وإشعار مسؤول.
- مهمة تستغرق ساعة وتستمر رغم إغلاق Desktop أو إعادة تشغيل API.

Celery الحالي يؤدي مهام صيانة ولا يقدم هذا العقد للمستخدم. AgentRun/Events بداية مفيدة، لكنها تحتاج state machine وديمومة كاملة.

### الحد الأدنى الصحيح المطلوب

1. كيان `Task` مستقل عن chat session، مع حالات صريحة:
   - draft / queued / running / waiting_approval / paused / succeeded / failed / cancelled / expired.
2. durable queue وworker lease/heartbeat، مع الاستئناف بعد crash وعدم تنفيذ الأفعال غير idempotent مرتين.
3. checkpoint لكل مرحلة، وتخزين plan، inputs، artifacts، tool results وpending approval.
4. retry policy per tool/error، backoff، timeout وdead-letter.
5. scheduling: manual/hourly/daily/weekly/cron، مع timezone وmisfire policy.
6. triggers لاحقاً: webhook، file arrival، ticket status، database event.
7. run history ومقارنة النتائج وإعادة تشغيل من خطوة آمنة.
8. approval inbox مركزية؛ لا تضيع الموافقة عند إغلاق التطبيق.
9. quotas منفصلة للمهام المجدولة، وحد أعلى للتوازي والقيمة المالية.
10. task owner وservice identity واضحان.

### معيار القبول

- إعادة تشغيل API/worker أثناء task لا تفقدها ولا تكرر فعل write خارجي.
- task ينتظر approval ساعات ثم يستأنف من checkpoint الصحيح.
- schedule يحترم timezone وDST والسياسة عند missed run.
- يمكن للمدير إيقاف كل schedules الخاصة بمصدر أو Profile متضرر.
- لكل تشغيل trace ونتائج وartifacts واستهلاك وتكلفة.

---

## P0-6 — Compliance Audit وData Governance

### الموجود حالياً

يوجد AuditLog وUserActivity وAgentRunEvents وKPIs، وهذا أفضل من غياب التدقيق. لكن قاعدة بيانات عادية وسطح Dashboard لا تكفيان وحدهما لإثبات عدم العبث أو تطبيق سياسات قانونية.

### المطلوب

1. event taxonomy ثابتة وversioned تشمل:
   - login/session/device
   - policy/profile/skill/MCP changes
   - model request metadata
   - tool call/result status
   - file read/write/delete
   - connector access/action
   - approval/deny/override
   - export/delete/retention operations
2. actor، subject، source IP/device، correlation ID، run/task/session IDs، policy version وreason.
3. append-only/tamper-evident storage: hash chain أو WORM destination أو log service مستقل.
4. exporter مستمر إلى Syslog/CEF/JSON وSIEM شائع، مع checkpoint وإعادة الإرسال.
5. فصل واضح بين:
   - **Audit/Compliance** للتحقيق.
   - **Usage Analytics** للتبني والتكلفة.
   - **Quality Evaluation** لجودة النتائج.
6. retention policies حسب نوع البيانات والقسم، مع purge قابل للإثبات.
7. legal hold وeDiscovery/export عند حاجة القطاعات المنظمة.
8. DLP قبل إرسال prompt/attachment/tool output إلى model أو connector.
9. data residency وmodel routing rules حسب تصنيف البيانات.
10. تشفير at-rest مع خيار customer-managed keys وتدوير دون فقد البيانات.

### معيار القبول

- سقوط SIEM لا يفقد الأحداث؛ تُخزن مؤقتاً وتُعاد بترتيب معقول وبدون تكرار ضار.
- أي تعديل إداري حساس له before/after وactor وcorrelation.
- يستطيع auditor القراءة والتصدير دون صلاحية تغيير الإعدادات.
- retention deletion تمسح النسخ الأساسية والـindexes والartifacts والcache وفق policy.
- لا تحتوي logs على prompts أو secrets افتراضياً؛ content capture اختيار صريح ومقيد.

---

## P0-7 — دورة حياة On‑Premise: Air‑gap، HA، Upgrade وDR

### لماذا يجب أن تتفوق المنصة هنا؟

Claude Cowork وCodex يقدمان خدمات سحابية وعملاء محليين، لكن المنصة تُباع لأن الشركة تريد امتلاك deployment داخل بيئتها. لذلك التفوق الحقيقي ليس نسخ cloud features، بل جعل التركيب والترقية والدعم آمنين وقابلين للتكرار.

### المطلوب

#### حزمة الإصدار

- صور OCI immutable وموقعة، SBOM، checksums وrelease manifest.
- private registry أو offline bundle قابل للنقل والتحقق.
- قائمة توافق بين Desktop/API/Runtime/schema/models/connectors.
- installer/upgrade tool idempotent مع preflight وpostflight.
- ترخيص offline أو grace period لا يوقف عمل العميل بسبب انقطاع الإنترنت.

#### الطوبولوجيا

- نمطان معلنان:
  1. Small deployment عبر Compose لعدد محدود.
  2. HA deployment عبر Kubernetes/Helm أو playbooks معتمدة، عند الحاجة الفعلية.
- PostgreSQL HA/managed internal DB، Redis HA إن كان جزءاً حرجاً، عدة API/workers، وshared/object storage.
- عدم الادعاء بأن إضافة replicas وحدها تحقق HA.

#### الترقية والرجوع

- database migration compatibility وexpand/contract عند الترقية دون توقف كبير.
- backup تلقائي قبل الترقية.
- rollback للإصدار عندما يكون schema compatible، وخطة forward-fix عندما لا يكون.
- canary/ring للـDesktop ولـProfiles/models/connectors.

#### الاستمرارية

- RPO/RTO tiers معلنة.
- restore drill دوري في بيئة فارغة.
- backup مشفر خارج cluster واختبار مفاتيح فك التشفير.
- runbook لفقد DB، Redis، storage، Runtime، certificate أو signing key.

### معيار القبول

- تثبيت كامل من bundle دون اتصال عام بالإنترنت.
- ترقية نسخة سابقة مدعومة مع حفظ البيانات والسياسات والاتصالات.
- restore من backup حديث في بيئة جديدة، وقياس RPO/RTO فعلي.
- فشل node واحد لا يوقف الخدمة في HA tier.
- كل artifact في release قابل للتحقق من التوقيع وSBOM.

---

## P0-8 — Observability وAgent Evaluation

### لماذا logs وKPIs الحالية لا تكفي؟

عندما يقول العميل “الوكيل لم ينفذ المهمة كما ينبغي”، يجب الإجابة بدقة:

- أي model/version استُخدم؟
- أي prompt/profile/skill/policy versions؟
- ما الأدوات التي استُدعيت؟
- أين انتظر؟ أين فشل؟
- هل السبب retrieval أم model أم connector أم approval أم quota؟
- هل الترقية الأخيرة خفّضت الجودة؟

### المطلوب

1. OpenTelemetry traces موحدة من Desktop → API → AgentService → Orchestrator → Runtime → model/MCP/tool.
2. trace/span IDs تعبر كل القنوات، بما فيها WebSocket وTelegram والمهام الخلفية.
3. Prometheus-compatible metrics على الأقل:
   - queue depth/wait time
   - TTFT وtotal latency
   - model/tool/MCP error rate
   - approval wait time
   - token/cost per profile/group/task
   - sandbox startup/cleanup failures
   - schedule success/misfire
4. structured logs مع redaction وsampling وسياسة retention.
5. evaluation datasets لكل Profile/use case، تشمل العربية والملفات والسياسات والأدوات.
6. offline regression قبل ترقية prompt/model/skill/connector.
7. production sampling مع user feedback وoutcome signals دون كشف بيانات حساسة.
8. canary + rollback gate إذا تدهورت الجودة أو التكلفة أو latency.

### معيار القبول

- من Task ID واحد يمكن تتبع الرحلة كاملة دون البحث اليدوي في عدة logs.
- ترقية Profile أو model لا تنتقل للإنتاج قبل اجتياز eval thresholds.
- dashboards تميز model failure عن MCP failure عن policy denial.
- telemetry تعمل بالكامل مع collectors داخل شبكة العميل.

---

## 7. فجوات مهمة من الدرجة P1

## P1-1 — مسار Git/Change Review للبروفايلات التقنية

التعديل الذري للملفات يحمي سلامة الكتابة، لكنه لا يوفر دورة مراجعة برمجية. للبروفايلات المسموح لها تعديل مشاريع برمجية، يجب إضافة:

- اكتشاف Git repository وحالته.
- branch/worktree مستقل لكل Task أو Run طويل.
- diff منظم لكل ملف وhunk، مع comments وموافقة قبل apply/commit.
- stage/revert/commit اختيارية، دون push تلقائي افتراضياً.
- tests/lint/build actions قابلة للتعريف لكل مشروع.
- review مستقل read-only على branch/commit/uncommitted diff.
- حماية user changes الموجودة قبل بدء الوكيل.

هذه القدرة لا تُفرض على موظفي HR أو المبيعات. تُقدم كـTechnical Workspace capability داخل Profile محدد.

### معيار القبول

- مهمتان متوازيتان لا تكتبان إلى checkout واحد.
- الوكيل لا يمسح تغييرات المستخدم غير المرتبطة.
- diff والمراجعة والاختبارات محفوظة مع Task.
- لا يحدث commit/push إلا وفق policy وموافقة واضحة.

---

## P1-2 — Artifact Engine للمستندات والجداول والعروض

Cowork يبرز لأنه لا يكتفي بنص؛ يسلم ملفاً قابلاً للاستخدام. المنصة تحتاج capabilities رسمية ومختبرة لـ:

- DOCX/PDF/XLSX/PPTX وCSV، مع قوالب الشركة.
- render/validate بصرياً ووظيفياً قبل التسليم.
- provenance: المدخلات، المصادر، إصدار القالب، ووقت الإنشاء.
- مكان artifacts مركزي بسياسة صلاحيات وretention، لا روابط محلية مؤقتة فقط.
- preview وموافقة قبل الكتابة إلى نظام خارجي أو مشاركة الملف.

لا يلزم تغيير تصميم Desktop. المطلوب محرك artifact خلف الواجهة الحالية، يظهر عبر نفس تجربة الملفات والمحادثة.

---

## P1-3 — Model Governance وRouting مؤسسي

المنصة تدعم مزودين وallowed providers ومفاتيح وتسعيراً، لكن المنتج المؤسسي يحتاج:

- model catalog مركزي مع status، context/output limits، modalities، location وتصنيف اعتماد.
- allowlist حسب group/profile/data classification.
- routing policy: primary/fallback، quality tier، cost ceiling وhealth circuit breaker.
- منع fallback إلى مزود خارجي عندما تكون البيانات مصنفة داخلية.
- version pinning أو approved aliases، مع canary/eval قبل الترقية.
- فصل credentials لكل provider/business unit، وتدوير مركزي.
- local model readiness/benchmark وقبول صريح لانخفاض الجودة مقابل data locality.
- show effective model decision في trace دون كشف secret.

---

## P1-4 — تعاون، ملكية وموافقات بشرية

الجلسة الخاصة بالمستخدم لا تكفي لكل عمليات الشركة. المطلوب:

- shared project/workspace حسب group مع صلاحيات view/comment/run/approve/admin.
- task owner وassignee وwatchers.
- handoff من موظف إلى آخر أو إلى فريق مراجعة مع حفظ السياق والآثار.
- approval inbox للمالية/القانون/الأمن، مع SLA وdelegation وexpiry.
- comments/mentions على plan، artifact، tool action أو diff.
- حفظ القرار البشري وسببه، لا مجرد زر approve.
- منع مشاركة secret أو credential ضمن سياق handoff.

لا يلزم بناء Slack منافس. يكفي نموذج collaboration مرتبط بالمهام والموافقات، ثم إشعارات عبر البريد/Teams/Slack/MCP عند الحاجة.

---

## P1-5 — Extensibility Supply Chain للـSkills وMCP وPlugins

الوضع الحالي يسمح بتعريف Skills وMCP servers، لكنه يحتاج دورة حياة حزم مؤسسية:

1. حزمة versioned تحتوي manifest واضحاً:
   - الاسم والإصدار والناشر
   - Skills/Profiles/MCP dependencies
   - permissions المطلوبة
   - supported platform versions
   - data destinations
2. توقيع وفحص provenance وhashes.
3. validation قبل النشر: schema، dependency، secrets scan، tool annotations واختبارات smoke.
4. states: draft/staging/approved/deprecated/revoked.
5. rollout حسب group وring، مع rollback.
6. منع employee من إضافة marketplace أو package source غير معتمد.
7. lockfile للإصدارات وعدم جلب dependency من الإنترنت أثناء runtime.
8. kill switch لموصل أو Skill متضررة.

الاقتراح الأدنى هو البناء فوق Profile/Skill/MCP الحالي، لا إنشاء نظام Plugin منفصل بالكامل منذ اليوم الأول.

---

## P1-6 — واجهات تكامل مستقرة: API، Webhooks، CLI وCI

FastAPI الحالي واجهة التطبيق، لكنه ليس تلقائياً External Platform API بعقد طويل الأجل. المطلوب:

- versioned public API منفصلة عن endpoints الخاصة بالواجهة.
- scoped service tokens وmTLS اختياري وidempotency keys.
- إنشاء Task، متابعة status/events، approvals، cancel، artifacts وusage.
- signed outgoing webhooks مع retry وreplay protection وdelivery log.
- CLI خفيفة للإدارة والتشغيل والdiagnostics داخل الشبكة.
- non-interactive runner للـCI.
- تكامل GitHub Enterprise/GitLab داخلي عند الحاجة: issue/merge request/review pipeline.
- compatibility policy وdeprecation window.

هذا يحول المنصة من تطبيق واحد إلى منصة يمكن للشركة دمجها في عملياتها دون استدعاء endpoints داخلية غير مستقرة.

---

## P1-7 — Device Trust وDesktop Fleet Management

بالإضافة إلى policy plane، تحتاج إدارة أسطول Desktop:

- device enrollment وهوية جهاز ومفتاح محلي protected.
- inventory: OS، app version، last seen، policy version، security posture الأساسي.
- remote session revoke وdevice disable.
- MDM deployment لـWindows/macOS، silent install/uninstall، update rings.
- certificate/proxy configuration داخلية.
- minimum version enforcement وemergency block.
- crash diagnostics اختيارية ومشفرة إلى collector داخلي.
- offline grace policy واضحة؛ لا يبقى جهاز مفصول قادراً على العمل إلى أجل غير محدود بسياسة قديمة.

لا ينبغي جمع بيانات endpoint أكثر من اللازم أو محاولة منافسة EDR. التكامل مع EDR/MDM الموجود أفضل من بناء واحد.

---

## 8. ميزات P2 مشروطة وليست أولوية عامة

## P2-1 — Computer Use

مفيد للأنظمة القديمة التي لا تملك API، لكنه أعلى خطراً وأقل ثباتاً من MCP/API. لا يُفعّل عاماً.

إذا أُضيف:

- allowlist للتطبيقات والنوافذ والمواقع.
- screenshot redaction ومناطق ممنوعة.
- تأكيد إلزامي للإرسال، الدفع، الحذف، النشر وتغيير الصلاحيات.
- تشغيل معزول أو VDI مخصص، لا جلسة المستخدم الكاملة افتراضياً.
- recording/audit مناسب مع سياسة خصوصية.
- replay-safe semantics ومنع تنفيذ مزدوج.

الترتيب الصحيح: API/connector أولاً، ثم browser automation، ثم computer use عند عدم وجود بديل.

## P2-2 — Remote/Mobile Dispatch

مفيد لمتابعة Task والموافقة واستلام النتائج، لكنه ليس P0. إذا طلبه العملاء:

- لا فتح مباشر من الإنترنت إلى Desktop.
- outbound rendezvous أو gateway داخلية مع device trust وMFA.
- إمكان تعطيله مؤسسياً.
- الموافقات الحساسة تحتاج step-up auth.
- يعرض أقل قدر من البيانات على الهاتف.

## P2-3 — ذاكرة طويلة المدى

`memory_settings` أو ذاكرة Runtime لا تكفي. الذاكرة المؤسسية يجب أن تكون:

- project/profile scoped، لا شخصية وعامة افتراضياً.
- قابلة للعرض والتعديل والحذف.
- لها مصدر ووقت وانتهاء وتصنيف.
- لا تتعلم secrets أو بيانات حساسة تلقائياً.
- تخضع لـretention/export/legal hold حسب نوعها.

ابدأ بذاكرة مشروع صريحة ومقتبسة من مصادر، لا “الوكيل يتذكر كل شيء”.

## P2-4 — تعدد الوكلاء

Hermes يدعم قدرات delegation، لكن فتحها دون حوكمة قد يضاعف التكلفة والمخاطر. المطلوب قبل التفعيل الواسع:

- graph واضح للـparent/child runs.
- budget وdepth/concurrency limits.
- منع tool privilege escalation: الابن لا يحصل على أكثر من الأب.
- منع الكتابة المتوازية إلى نفس المورد دون lock/worktree.
- جمع trace والتكلفة والapprovals في Task الأصلية.

---

## 9. ما الذي لا أوصي بنسخه من المنافسين الآن؟

1. **Hosted cloud execution كافتراض وحيد:** يناقض سبب شراء النسخة On‑Premise. يمكن توفير hybrid mode لاحقاً، لكن local-first يبقى العقد الأساسي.
2. **Marketplace عام مفتوح:** يزيد خطر supply chain. البداية الصحيحة catalog داخلي موقّع يوافق عليه المدير.
3. **وصول Web/Browser/Computer Use واسع افتراضياً:** يجب أن يكون deny-by-default ومخصصاً لكل Profile.
4. **ذاكرة شخصية شاملة غير مضبوطة:** تصطدم بالخصوصية والretention وحق الحذف.
5. **جمع محتوى المحادثات كاملاً في telemetry:** يزيد نطاق التسريب. metadata افتراضي، والمحتوى opt-in مشروط.
6. **تحويل كل chat إلى multi-agent:** يكلف أكثر ويصعب تفسيره. delegation يستخدم فقط عندما يثبت eval أنه مفيد.
7. **بناء عشرات connectors قبل وجود framework للحياة والأمان:** خمسة connectors موثوقة مع ACL وsync أفضل من خمسين demo connectors.
8. **نسخ واجهات المنافسين أو تغيير التصميم الحالي:** لا توجد حاجة هندسية لذلك. الفجوات أغلبها control plane وruntime وoperations ويمكن إدخالها ضمن التصميم القائم.

---

## 10. المعمارية المستهدفة المقترحة

لا تحتاج المنصة إعادة كتابة. التطور الصحيح هو إضافة planes واضحة حول المكونات الحالية:

```text
┌───────────────────────────────────────────────────────────────┐
│ Company Identity & Device Plane                               │
│ OIDC/SAML/SCIM • Groups/RBAC • Device trust • Managed policy │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│ Existing Control Plane: FastAPI + Dashboard                   │
│ Users • Profiles • Skills • MCP • Tasks • Approvals • Usage  │
└───────────────┬───────────────────────────────┬───────────────┘
                │                               │
┌───────────────▼──────────────┐  ┌────────────▼────────────────┐
│ Knowledge & Integration Plane│  │ Durable Orchestration Plane │
│ Sync • ACL • Index • Citation│  │ Queue • Schedule • State    │
│ MCP • Connectors • Secrets   │  │ Checkpoint • Retry • Events │
└───────────────┬──────────────┘  └────────────┬────────────────┘
                └────────────────┬──────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────┐
│ Execution Plane                                                │
│ Hermes Agent Loop • Per-run Sandbox • Egress • Secret broker  │
│ Desktop local mediation • Optional Git/Computer Use           │
└────────────────────────────────┬──────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────┐
│ Governance, Observability & Lifecycle                          │
│ Audit/SIEM • OTEL/Metrics • Evals • Backup/DR • Upgrade/Airgap│
└───────────────────────────────────────────────────────────────┘
```

المكونات الحالية تبقى في مكانها:

- FastAPI يصبح control plane المؤسسي.
- Dashboard يبقى سطح الإدارة ويضاف إليه configuration، tasks، compliance وoperations ضمن تصميمه الحالي.
- Desktop يبقى سطح الموظف ووسيط الملفات والموافقات؛ لا يحتاج إعادة تصميم.
- Hermes يبقى agent engine؛ لا يُحمّل مسؤولية identity/governance/catalog.
- MCP يبقى معيار ربط الأدوات، بينما تضيف المنصة policy، credentials، audit وknowledge lifecycle حوله.

---

## 11. خارطة تنفيذ مرتبة حسب القيمة والمخاطر

هذه ليست تقديرات زمنية؛ هي بوابات متتابعة. لا تبدأ المرحلة التالية قبل قبول السابقة.

## المرحلة A — Enterprise Trust Foundation

**النطاق:**

1. OIDC/SAML + groups + RBAC + service accounts.
2. SCIM/JIT أو تكامل directory حسب أول عميل.
3. signed managed policy للـDesktop والـRuntime.
4. device enrollment/version enforcement/revocation.
5. egress enforcement لكل Profile/Run.
6. audit taxonomy + SIEM exporter.

**بوابة الخروج:**

- اختبار deprovisioning وeffective permissions.
- محاولة تجاوز policy من Desktop وAPI تفشل.
- أحداث التدقيق تصل SIEM دون فقد.
- security review لنموذج التهديد ومفاتيح التشفير.

## المرحلة B — Safe Durable Execution

**النطاق:**

1. Task state machine وdurable queue/checkpoints.
2. scheduled tasks وapproval inbox.
3. per-run execution sandbox وsecret broker.
4. end-to-end OTEL traces وmetrics.
5. quotas/concurrency/cost policy للمهام.

**بوابة الخروج:**

- crash/restart/cancel/retry/idempotency tests.
- isolation/leakage/resource exhaustion tests.
- schedule/timezone/misfire tests.
- load/soak مع SLO معلن.

## المرحلة C — Governed Enterprise Knowledge

**النطاق:**

1. connector framework و2–5 مصادر يحددها السوق الأول.
2. ACL-aware indexing/retrieval/citations.
3. sync health/delete propagation/DLP.
4. credentials lifecycle وconnector kill switch.
5. artifact storage/retention.

**بوابة الخروج:**

- permission leakage suite.
- freshness/deletion/reindex tests.
- citations accuracy evaluation.
- تشغيل كامل داخل شبكة معزولة.

## المرحلة D — Quality and Extensibility

**النطاق:**

1. evaluation datasets/gates/canary/rollback.
2. signed versioned Skill/MCP package lifecycle.
3. model catalog/routing/fallback governance.
4. public automation API/webhooks/CLI.
5. artifact engine للمستندات والجداول والعروض.

**بوابة الخروج:**

- لا ترقية Profile/model/package دون eval وcompatibility checks.
- rollback package/model/profile مثبت.
- API contract/versioning/security tests.

## المرحلة E — Specialized Workspaces

**حسب العملاء فقط:**

1. Git/worktree/review للمطورين.
2. Computer Use لبيئة VDI أو تطبيقات محددة.
3. Remote/mobile approval and dispatch.
4. controlled multi-agent delegation.

---

## 12. ترتيب المنتج المقترح: Must / Should / Later

### Must Have قبل بيع Enterprise On‑Premise واسع

- SSO/directory lifecycle/groups/RBAC.
- managed policy وdevice/version enforcement.
- per-run isolation وegress enforcement.
- durable/scheduled tasks مع approvals وresume.
- SIEM export وretention/data governance أساسية.
- HA/air-gap/upgrade/rollback/restore drill حسب tier المباع.
- OTEL/metrics وevaluation gate.

### Should Have بعد أول أساس آمن

- ACL-aware knowledge connectors.
- model catalog/routing governance.
- signed/versioned Skills/MCP packages.
- shared tasks/projects/approval inbox.
- artifact engine.
- stable API/webhooks/CLI.

### Later / حسب القطاع

- Git worktrees/review.
- Computer Use.
- Remote/mobile dispatch.
- broad multi-agent workflows.
- personal long-term memory.

> إذا كانت أولى الشركات المستهدفة تعتمد استخداماً معرفياً مبنياً على SharePoint/Confluence، ينتقل Enterprise Knowledge إلى المرحلة A/B. وإذا كانت المنصة ستباع أساساً لفرق التطوير، ينتقل Git/Worktree/Review إلى P0/P1 مبكر.

---

## 13. قرارات منتج يجب حسمها قبل خطة التنفيذ التفصيلية

لا يلزم حسمها لقراءة هذا التقرير، لكنها تغيّر الأولويات:

1. ما القطاعات الثلاثة الأولى: حكومة، بنوك، صحة، مصانع، شركات تقنية أم خدمات مهنية؟
2. هل العقد “لا اتصال خارجي إطلاقاً”، أم يسمح بمزودي model خارجيين عبر egress proxy؟
3. هل Desktop إلزامي، أم توجد فئة مستخدمين تعمل من Web فقط؟
4. هل أول use case أعمال معرفة، تطوير برمجيات، support operations أم خليط؟
5. ما أنظمة الهوية الأكثر شيوعاً لدى العملاء: Entra ID، Keycloak، ADFS، Okta أم LDAP مباشر؟
6. ما مصادر المعرفة الأعلى أولوية؟
7. هل مطلوب Kubernetes/HA من أول عميل، أم Compose tier مدعوم يكفي للبداية؟
8. من يتحمل تشغيل النماذج المحلية وسعتها: فريقك أم IT لدى العميل؟
9. ما متطلبات retention والتدقيق وRPO/RTO لكل tier تجاري؟

---

## 14. مخاطر يجب تجنبها أثناء الإضافة

| الخطر | أثره | الوقاية |
|---|---|---|
| تحويل Hermes إلى control plane شامل | اقتران قوي وصعوبة ترقية المحرك | إبقاء الهوية والسياسة والحوكمة في المنصة وتمرير effective runtime contract فقط |
| اعتبار MCP هو كل integration strategy | غياب ACL/sync/freshness/governance | فصل Action MCP عن Knowledge Connector |
| تنفيذ scheduling كـcron يستدعي chat endpoint | تكرار أفعال وضياع state والموافقات | Task state machine + durable queue + idempotency |
| sandbox على مستوى الخدمة فقط | تسريب بين التشغيلات وتأثير متبادل | per-run isolation وephemeral workspace |
| SSO بلا deprovisioning/groups | حسابات يتيمة وإدارة يدوية | SCIM/JIT + group mapping + session revocation |
| تخزين كل prompts في logs | توسع نطاق البيانات الحساسة | metadata افتراضياً، redaction وموافقة على content capture |
| بناء HA شكلي | تعطل DB/storage يبقي نقطة فشل | تعريف dependency topology واختبار failover فعلي |
| كثرة connectors غير المختبرة | مخاطر supply chain وتسريب | عدد صغير، signing، permissions واختبارات عقد |
| model upgrade تلقائي | تراجع صامت في الوظائف | pin/canary/evals/rollback |
| السماح للمستخدم بتجاوز policy عند offline | صلاحيات قديمة أو أوسع | signed cache بمدة صلاحية وfail-closed للحساس |
| إعادة تصميم الواجهات أثناء الإصلاح | مخاطرة غير مرتبطة بالقيمة | إضافة القدرات داخل التصميم الحالي كما طلب صاحب المشروع |

---

## 15. النتيجة النهائية

المنصة تملك أساساً أفضل من مشروع Agent عادي: Runtime محكوم، Desktop يتعامل مع الملفات بحذر، control plane إداري، حصص وتكلفة، وMCP مُدار من المدير. لذلك لا أوصي بإعادة بناء المنتج ولا باستبدال Hermes ولا بتغيير التصميم.

الفجوة مع Claude Cowork وChatGPT Codex هي أن المنافسين أحاطوا الوكيل بطبقات ناضجة من العزل، المهام المستمرة، الحزم، السياسات، العمل على الملفات/المشاريع والتكامل المؤسسي. وبالنسبة لمنصة On‑Premise، يجب إضافة طبقات أكثر صرامة منهم في الهوية، الجهاز، التدقيق، دورة الإصدار، الاستعادة والعمل دون إنترنت.

الترتيب الاستراتيجي الصحيح هو:

> **Trust & Governance → Durable Isolated Execution → Governed Knowledge → Quality & Extensibility → Specialized UX**

وليس:

> مزيد من الأدوات العامة → مزيد من الوكلاء → Computer Use → ثم محاولة إضافة الأمان لاحقاً.

إذا نُفذت الأولويات P0 بالحد الأدنى المحدد، ستتحول المنصة من “Agent platform جيدة تعمل داخل الشركة” إلى **Enterprise On‑Premise Agent Operating Platform قابلة للاعتماد والتشغيل والدعم والتوسع**. عندها تصبح ميزتها التنافسية الحقيقية ليست تقليد Cowork أو Codex، بل تقديم تجربة قريبة منهما مع سيادة بيانات وتشغيل وسياسات تحت سيطرة العميل.

---

## 16. الأدلة والمصادر

### 16.1 مصادر داخلية تم فحصها

- `app/main.py` ومسارات `app/api/`.
- `app/services/agent_service.py` و`app/services/agent_runtime.py` و`app/services/hermes_orchestrator.py`.
- `app/hermes_orchestrator_app.py` و`app/local_hermes_runtime_app.py`.
- Models وSchemas وترحيلات Alembic، بما فيها MCP وAgentRun وTokenReservation.
- `desktop/src/main/` و`desktop/src/preload/` و`desktop/src/renderer/scripts/`.
- `frontend/src/app/` وطبقة API في Dashboard.
- `docker-compose.production.yml` و`docker-compose.release.yml` وملفات CI/deploy.
- `docs/PRODUCTION_SOLUTION_REVIEW_AR_2026-07-16.md`.
- `docs/PRODUCTION_REMEDIATION_EXECUTION_AR_2026-07-23.md`.
- `docs/DESKTOP_COWORK_GAP_ANALYSIS_2026-06-22.md`.

### 16.2 Claude Cowork — مصادر Anthropic الرسمية

- [Claude Cowork product overview](https://www.anthropic.com/product/claude-cowork)
- [Get started with Claude Cowork](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork)
- [Claude Cowork architecture overview](https://support.claude.com/en/articles/14479288-claude-cowork-architecture-overview)
- [Schedule recurring tasks in Claude Cowork](https://support.claude.com/en/articles/13854387-schedule-recurring-tasks-in-claude-cowork)
- [Use Claude Cowork on Team and Enterprise plans](https://support.claude.com/en/articles/13455879-use-claude-cowork-on-team-and-enterprise-plans)
- [Custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Use plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)
- [Manage plugins for your organization](https://support.claude.com/en/articles/13837433-manage-plugins-for-your-organization)
- [How Anthropic contains Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude)
- [Set up single sign-on](https://support.claude.com/en/articles/13132885-set-up-single-sign-on-sso)
- [SCIM sync for Enterprise organizations](https://support.claude.com/en/articles/14499648-how-scim-sync-works-for-enterprise-organizations)
- [Roles and permissions](https://support.claude.com/en/articles/9267276-roles-and-permissions)
- [Claude Enterprise plan](https://support.claude.com/en/articles/9797531-what-is-the-enterprise-plan)

### 16.3 ChatGPT Codex — مصادر OpenAI الرسمية

- [Agent approvals and security](https://learn.chatgpt.com/docs/agent-approvals-security)
- [Projects and chats](https://learn.chatgpt.com/docs/projects)
- [Long-running work](https://learn.chatgpt.com/docs/long-running-work)
- [Scheduled tasks](https://learn.chatgpt.com/docs/automations)
- [Code review](https://learn.chatgpt.com/docs/code-review)
- [Integrated terminal](https://learn.chatgpt.com/docs/integrated-terminal)
- [Local environments](https://learn.chatgpt.com/docs/environments/local-environment)
- [Git worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)
- [Remote connections](https://learn.chatgpt.com/docs/remote-connections)
- [MCP](https://learn.chatgpt.com/docs/extend/mcp)
- [Plugins](https://learn.chatgpt.com/docs/plugins)
- [Hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk)
- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration)
- [Groups and provisioning](https://learn.chatgpt.com/docs/enterprise/groups-and-provisioning)
- [Governance](https://learn.chatgpt.com/docs/enterprise/governance)
- [Compliance API and audit events](https://learn.chatgpt.com/docs/enterprise/compliance-api)
- [Workspace analytics](https://learn.chatgpt.com/docs/enterprise/workspace-analytics)
- [Windows app deployment](https://learn.chatgpt.com/docs/enterprise/windows-deployment)

> جميع المقارنات الخارجية تمثل حالة الوثائق الرسمية المتاحة في تاريخ التقييم. ميزات المنافسين قد تتغير، وبعضها beta أو مرتبط بخطة/منطقة/سطح استخدام محدد؛ لذلك استُخدمت كمرجع نمط وقدرة، لا كضمان تعاقدي دائم.
