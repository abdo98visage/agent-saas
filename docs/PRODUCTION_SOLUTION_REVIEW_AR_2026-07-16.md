# مراجعة جاهزية AgentSaaS للإنتاج

> **تحديث التنفيذ (2026-07-23):** نُفذت المعالجات القابلة للتطبيق داخل المستودع ووُثقت نتائج الاختبارات والبنود الخارجية المتبقية في `docs/PRODUCTION_REMEDIATION_EXECUTION_AR_2026-07-23.md`. تبقى هذه الوثيقة مرجع المشاكل والخطة الأصلية.

**تاريخ المراجعة:** 2026-07-16  
**النطاق:** Agent Runtime، واجهة FastAPI والخدمات الخلفية، لوحة الإدارة Next.js، تطبيق Desktop/Electron، قاعدة البيانات، النشر والتشغيل والنسخ الاحتياطي  
**خارج النطاق عمداً:** التصميم، الثيم، الألوان، وتجربة الواجهة البصرية  
**نوع المراجعة:** مراجعة كود وبنية وتشغيل Production Readiness، وليست مراجعة شكلية أو رأياً عاماً

---

## 1. الخلاصة التنفيذية

المشروع يملك أساساً وظيفياً جيداً، وأجزاؤه الثلاثة مترابطة فعلاً وليست مجرد نماذج أولية. البناء الإنتاجي للـ Dashboard نجح، وكود Python مرّ بفحص الترجمة، كما توجد عناصر صحيحة مثل تشفير مفاتيح المزود، تذاكر WebSocket قصيرة العمر، فصل شبكة Hermes الداخلية، سجل تدقيق، وملفات نشر ونسخ احتياطي.

لكن **النسخة الحالية لا أنصح باعتبارها Production Ready بعد**. القرار المهني هو:

> **Conditional No-Go** إلى أن تُغلق جميع عناصر `P0` ويُنجز الحد الأدنى المحدد من عناصر `P1` واختبارات القبول.

السبب ليس التصميم أو جودة الوظائف الظاهرة، بل وجود مخاطر خلف السلوك الطبيعي قد تظهر بعد النشر أو مع تعدد المستخدمين، وأبرزها:

1. Agent Runtime يعمل بصلاحيات واسعة ويحصل على كامل أسرار المنصة، ثم يشغّل Hermes بوضع `--yolo` مع مدخلات غير موثوقة.
2. جلسة Desktop تنتهي بعد 8 ساعات، لكن التطبيق لا يملك Login/Refresh صالحاً بعد التفعيل؛ ما يحول انتهاء الجلسة إلى إعادة دعوة الموظف.
3. سياسات الأدوات والموافقات المعرفة في Profile لا تُفرض فعلياً في Cowork، ويمكن للعميل اختيار وضع الموافقة.
4. ترحيلات النسخة المحلية الحالية تحتوي رأسين Alembic، وبالتالي `alembic upgrade head` سيفشل عند النشر التالي.
5. Runtime المحلي يحجب event loop أثناء تنفيذ Hermes، والـ streaming المعلن ليس streaming حقيقياً.
6. توجد ملفات بيئة تاريخية وملفات PostgreSQL مؤقتة متتبعة داخل Git؛ بعض قيم Supabase التاريخية تبدو غير placeholder ويجب التعامل معها كحادث أسرار إلى أن يثبت العكس.
7. الصور تبدو مدعومة في الواجهة والتخزين، لكنها لا تصل إلى Hermes، كما أن حد WebSocket الإنتاجي المولّد لا يسمح عملياً بصور base64.
8. مسار ملفات Desktop قابل لتجاوز حدود Workspace عبر symlink، والـ offline queue قد يعيد الرسائل إلى محادثة أو مشروع مختلف.

هذه العيوب لا تنفي أن الوظائف الأساسية جرى اختبارها وتعمل، لكنها تمنع ضمان الأمان والعزل والاستمرارية تحت حمل إنتاجي أو عند حدوث فشل جزئي.

---

## 2. منهجية وحدود المراجعة

تمت مراجعة نحو:

- 51 ملف Backend بما يقارب 7,333 سطر كود/إعداد.
- 40 ملف Frontend بما يقارب 5,891 سطراً.
- 11 ملف Desktop بما يقارب 4,103 أسطر.
- 18 ملف نشر وتشغيل بما يقارب 2,547 سطراً.
- 15 ملف migrations بما يقارب 642 سطراً.
- ملفات Docker/Compose/Nginx/Caddy وملفات install/backup/restore وCI الموجودة.

ركزت المراجعة على: حدود الثقة، العزل بين المستأجرين، دورة المصادقة، العقود بين الخدمات، التزامن، الفشل الجزئي، سلامة البيانات، الهجرات، الحصص والفوترة، قابلية التشغيل والمراقبة، وسلامة إصدار Desktop.

### حالة نسخة العمل

المراجعة تمت على **حالة Working Tree الحالية**، وهي تحتوي تعديلات غير ملتزمة، منها دعم attachments وترحيل جديد واختبار جديد. لذلك:

- ما يخص `add_message_attachments.py` موصوف كمانع **للنشر القادم** إذا دُمج كما هو.
- لم ألغِ أو أعدّل أي كود موجود للمستخدم.
- أرقام الأسطر أدلة على snapshot المراجع وقد تتغير بعد التعديل.

### مقياس الأولوية

| المستوى | المعنى |
|---|---|
| `P0` | مانع إنتاج أو ثغرة/فقد بيانات محتمل؛ يجب إغلاقه قبل النشر |
| `P1` | خلل مرتفع الأثر سيظهر مع الاستخدام الحقيقي أو الفشل أو التوسع؛ يجب إدخاله في إصدار الجاهزية |
| `P2` | تحسين مهم للصلابة والصيانة والتشغيل؛ لا يُهمل لكن يمكن جدولته بعد الموانع |

---

## 3. نقاط القوة الموجودة فعلاً

من المهم الحفاظ على هذه الجوانب أثناء الإصلاح:

- استخدام `token_version` لإبطال الجلسات القديمة عند تغيير حالة الموظف.
- تذكرة منفصلة وقصيرة العمر للـ WebSocket مع فحص `purpose == "ws"` في `app/api/websocket_chat.py:83-94`.
- تشفير مفاتيح مزودي LLM المخزنة بدلاً من حفظها كنص واضح.
- وجود شبكة داخلية لخدمات Hermes وعدم نشر منافذ Runtime مباشرة في إعدادات Compose الأساسية.
- التحقق من ملكية Session في منافذ REST/WS المعتادة قبل بدء المحادثة.
- وجود audit log وKPI وAgent runs وhealth/readiness endpoints كأساس تشغيلي جيد.
- وجود scripts للنشر والنسخ والاستعادة وفحص readiness، حتى لو احتاجت تقوية.
- نجاح بناء Next.js الإنتاجي وفحص TypeScript.
- عدم وجود خطأ syntax في ملفات JavaScript الخاصة بـ Desktop أثناء المراجعة.

التوصيات التالية تهدف إلى تقوية هذه البنية، لا إلى إعادة تصميم المنصة.

---

## 4. موانع الإنتاج `P0`

### P0-01 — أسرار وبيانات تشغيلية متتبعة في Git

**الدليل**

- توجد أربعة ملفات متتبعة تحت `.history/.env_*` وتحتوي أسماء مفاتيح مثل `SECRET_KEY` و`SUPABASE_SERVICE_KEY`.
- أظهر الفحص دون طباعة القيم أن عدة قيم Supabase في ثلاثة ملفات تبدو غير فارغة وغير placeholder.
- يوجد **2,769 ملفاً** متتبعاً تحت `.tmp-pgdata/**`/بيانات PostgreSQL المؤقتة، بما فيها `postmaster.pid`.
- حجم Git الحالي كبير بصورة غير طبيعية: loose objects تقارب 239.68 MiB وpacks تقارب 113.61 MiB.

**الأثر**

- إذا دُفع المستودع إلى remote أو نُسخ إلى CI/جهاز مطور، يجب اعتبار مفاتيح Supabase مكشوفة حتى إن كانت قديمة.
- صفحات PostgreSQL قد تحتوي رسائل أو مستخدمين أو بيانات حساسة لا يمكن ضمان محوها بمجرد حذف الملفات في commit جديد.
- تضخم clone/CI وارتفاع احتمال تسريب بيانات حقيقية في build artifacts أو نسخ المستودع.

**الإجراء المطلوب**

1. إلغاء/تدوير كل مفاتيح Supabase الموجودة تاريخياً، وفحص بقية الأسرار لدى المزودين.
2. إزالة `.history` و`.tmp-pgdata` من الفهرس، ثم تنظيف تاريخ Git بأداة مثل `git filter-repo` بالتنسيق مع كل مستخدمي المستودع.
3. تشغيل secret scanner على كامل التاريخ، وليس HEAD فقط.
4. اعتبار أي بيانات إنتاجية كانت داخل PostgreSQL حادث خصوصية وتقييم نطاقها.

**معيار القبول**

- لا يعثر secret scanner على أسرار فعالة في كامل التاريخ المنظف.
- جميع المفاتيح المحتمل كشفها مدورة ومثبت تاريخ إبطالها.
- `git ls-files '.tmp-pgdata/**' '.history/.env*'` لا يعيد شيئاً.

### P0-02 — كسر حدود الثقة في Agent Runtime

**الدليل**

- خدمة `hermes-runtime` تستقبل كامل `.env.production` عبر `env_file` في `docker-compose.production.yml:124-133` و`docker-compose.release.yml:123-132`.
- التطبيق ينسخ `os.environ` للعملية في `app/local_hermes_runtime_app.py:111-128`.
- Hermes يُشغّل مع `--yolo` في `app/local_hermes_runtime_app.py:509-530`.
- كل من `Dockerfile` و`Dockerfile.hermes-runtime` لا يعرّفان `USER` غير root.

**الأثر**

رسالة موظف، محتوى مستودع داخل Workspace، أو skill prompt خبيث قد يوجّه الوكيل لقراءة البيئة. وبسبب وجود أسرار قاعدة البيانات وFernet وJWT وSMTP وTelegram في البيئة مع شبكة صادرة، تصبح prompt injection المحتملة مساراً لاستخراج أسرار المنصة نفسها، لا مجرد بيانات مشروع المستخدم.

**الإجراء المطلوب**

- إعطاء Runtime متغيرات الحد الأدنى فقط؛ ممنوع تمرير `DATABASE_URL` و`SECRET_KEY` و`FERNET_KEY` وأسرار SMTP/Telegram.
- تشغيله كمستخدم غير root، مع `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, tmpfs محدود، وحدود CPU/RAM/PIDs.
- استبدال `--yolo` بسياسة أدوات صريحة ومفروضة من الخادم، أو عزل كل run في sandbox/حاوية قصيرة العمر.
- تقييد egress إلى مزود LLM والخدمات المسموحة فقط، ومنع الوصول إلى metadata/internal control plane.
- عدم حقن API key في prompt أو args، وتقليل مدة بقائه في العملية.

**معيار القبول**

- اختبار اختراق prompt injection لا يستطيع قراءة أي سر للمنصة أو الاتصال بعنوان غير allowlist.
- `id` داخل حاوية Runtime ليس root، ولا توجد Linux capabilities إضافية.
- قائمة البيئة الموثقة للـ Runtime لا تتضمن أسرار control plane.

### P0-03 — ترحيلات Alembic ذات رأسين في النسخة الحالية

**الدليل**

- `migrations/versions/add_message_attachments.py:13` يضع `down_revision = "merge_alert_and_skill_heads"`.
- `migrations/versions/add_profile_ids_to_user_api_keys.py:13` يضع الأب نفسه.
- Compose يشغّل `alembic upgrade head` عند بدء API.

**الأثر**

بعد دمج الترحيلين ستوجد شعبتان نهائيتان، و`upgrade head` لا يستطيع اختيار رأس وحيد. النتيجة: فشل تشغيل API في النشر التالي أو اختلاف schema بين البيئات إذا جرى الالتفاف يدوياً.

**الإجراء المطلوب**

- جعل أحد الترحيلين تابعاً للآخر أو إضافة merge revision صريح بعدهما.
- إضافة CI gate يشغّل `alembic heads` ويتأكد من رأس واحد، ثم يختبر upgrade من قاعدة فارغة ومن نسخة الإصدار السابق، ثم downgrade/restore حسب السياسة.
- فصل migration job عن تشغيل كل replica لتجنب السباق عند التوسع.

**معيار القبول**

- `alembic heads` يعيد رأساً واحداً فقط.
- ترقية نسخة مماثلة للإنتاج تنجح مرة واحدة، وتطبيق API يبدأ بعدها دون تعديل يدوي.

### P0-04 — دورة جلسة Desktop غير قابلة للاستمرار

**الدليل**

- عمر access token الافتراضي 480 دقيقة في `app/core/config.py:46`.
- التفعيل يستهلك invite token ويزيله في `app/api/auth.py:146-193`.
- Desktop ينفذ activation في `desktop/src/renderer/scripts/03-workspace-and-chat.js:629-668`، ولا يوجد مسار Login أو Refresh Token فعلي.
- عند 401/403 تُمسح الجلسة ويعود التطبيق إلى شاشة التفعيل في `desktop/src/renderer/scripts/01-state-and-i18n.js:481-503`.
- إصدار دعوة جديدة يعطّل/يلغي السابقة في `app/api/admin.py:184-192` و`256-285`.

**الأثر**

الموظف الذي فُعّل بنجاح سيفقد الدخول بعد 8 ساعات، ولا يمكنه إعادة المصادقة بصورة طبيعية. عملياً يصبح كل انتهاء token عملية دعم إداري وإصدار دعوة جديدة، وقد تتأثر جلسات أخرى.

**الإجراء المطلوب**

- اعتماد access token قصير + refresh token دوّار محفوظ عبر OS secure storage، مع device/session revocation.
- أو إضافة Login واضح للموظف بعد activation الأول؛ التفعيل يجب أن يثبت الجهاز/الحساب، لا أن يكون آلية الدخول اليومية.
- فصل أخطاء الشبكة وWS ticket عن “الجلسة غير صالحة”.
- إزالة fallback الذي يعيد access JWT عادياً عندما يفشل `/ws-token` في `desktop/src/renderer/scripts/02-projects-and-settings.js:528-540`؛ backend يرفضه لأنه بلا purpose خاص.

**معيار القبول**

- اختبار زمني يتجاوز انتهاء access token ويجدد الجلسة دون دعوة إدارية.
- انقطاع `/ws-token` المؤقت لا يمسح جلسة مستخدم صالحة.
- يستطيع المدير إبطال جهاز واحد أو كل الجلسات بصورة مدققة.

### P0-05 — سياسات الأدوات والموافقات موجودة في البيانات لكنها غير مفروضة

**الدليل**

- Profile يخزن `allowed_tools`, `approval_required_tools`, `allowed_mcp_servers`, و`memory_settings` في `app/api/admin.py:470-542`.
- Cowork يستخدم قائمة أدوات ثابتة في `app/api/websocket_chat.py:35-37` و`410-413`.
- العميل يرسل `approval_mode`، والخادم يقبل القيمة ويقرر طلب الموافقة على أساسها في `app/api/websocket_chat.py:455-500` و`718-721`.
- Hermes المحلي يعمل أيضاً بوضع `--yolo`.

**الأثر**

قد تعرض لوحة الإدارة أن profile مقيد أو أن أداة تحتاج موافقة، بينما التنفيذ لا يلتزم بهذه السياسة. يستطيع عميل معدل اختيار `full_access`، فتتحول إعدادات الحوكمة إلى “config theatre” بدلاً من control أمني.

**الإجراء المطلوب**

- حساب policy الفعلية حصراً في الخادم من user/profile/tenant؛ لا تُقبل صلاحية موسعة من العميل.
- تقاطع الأدوات القادمة من Runtime مع allowlist الخاصة بالـ Profile.
- فرض approval-required server-side مع nonce مرتبط بالـ run/action ومدة صلاحية ومنع replay.
- رفض MCP server غير مسموح قبل إرساله إلى Runtime.

**معيار القبول**

- عميل معدل يطلب `full_access` لا يستطيع تجاوز Profile policy.
- اختبارات contract تغطي كل tool: مسموح، ممنوع، يحتاج موافقة، وموافقة منتهية/معادة الاستخدام.

### P0-06 — تجاوز حدود Workspace في Desktop عبر symlink

**الدليل**

- فحص containment في `desktop/src/main/main.js:271-295` يعتمد على المسار النصي/المحلول المعتاد، بينما عمليات القراءة والكتابة والحذف وإعادة التسمية اللاحقة لا تتحقق من `realpath` لكل مكوّن.

**الأثر**

يمكن إنشاء symlink داخل Workspace يشير إلى ملف خارجه، ثم تمرير المسار “الداخلي” إلى IPC. هذا يسمح للوكيل أو المشروع الخبيث بقراءة/تعديل ملفات خارج مجلد المشروع بصلاحيات مستخدم Desktop.

**الإجراء المطلوب**

- استخدام `realpath` للجذر والهدف والأب الموجود، ورفض أي symlink/reparse point يخرج عن الجذر.
- فتح الملفات بطريقة تقلل TOCTOU حيث يدعم النظام ذلك، وإعادة الفحص مباشرة قبل العملية.
- سياسة مستقلة للقراءة والكتابة والحذف، مع منع المسارات الحساسة حتى لو ربطت داخل المشروع.

**معيار القبول**

- اختبارات Windows junction/symlink وmacOS/Linux symlink تفشل بأمان للقراءة والكتابة والحذف وإعادة التسمية خارج الجذر.

### P0-07 — Agent Runtime يحجب الخادم والـ streaming غير حقيقي

**الدليل**

- endpoint غير متزامن يستدعي `subprocess.run` المتزامن في `app/local_hermes_runtime_app.py:495-540`.
- مسار stream ينتظر انتهاء `_run_hermes` بالكامل ثم يقسّم النص إلى جزأين في `app/local_hermes_runtime_app.py:575-626`.

**الأثر**

- run واحد طويل يحجب event loop، فيؤخر health checks وكل المستخدمين على نفس runtime.
- المستخدم لا يتلقى أول token قبل نهاية التنفيذ، رغم أن API والـ UI يتعاملان معه كـ streaming.
- عند التوسع سترتفع latency ويحدث head-of-line blocking وقد تعيد المنصة تشغيل حاوية سليمة ظاهرياً.

**الإجراء المطلوب**

- استخدام `asyncio.create_subprocess_exec` وقراءة stdout/stderr تدريجياً، أو worker queue/process pool مع حد concurrency واضح.
- بث أحداث حقيقية فور وصولها، وإلغاء subprocess عند disconnect/timeout.
- إضافة per-run timeout، kill tree، وحصة CPU/RAM، وqueue backpressure.

**معيار القبول**

- Run طويل لا يمنع `/health` ولا run ثانياً ضمن حد concurrency.
- Time-to-first-token قابل للقياس ويحدث قبل نهاية العملية.
- قطع العميل يلغي التنفيذ ولا يترك process يتيم.

### P0-08 — مسار التثبيت Release غير صالح بالافتراضات الحالية

**الدليل**

- `docker-compose.release.yml:21,47,63,80,95,124` يستخدم افتراضياً صوراً من `ghcr.io/example/...:latest`.
- `deploy/install.sh:142-144` يولّد الافتراضات نفسها.
- readiness check لا يرفض namespace `ghcr.io/example` ولا tag `latest`.

**الأثر**

تعليمات “التثبيت” الافتراضية ستفشل في pull أو قد تنشر artifact غير ثابت إذا استُبدلت الصور مع بقاء `latest`. هذا مانع لإعادة إنتاج النشر والاستعادة.

**الإجراء المطلوب**

- استبدال namespace الوهمي بسجل فعلي وفرض tag إصدار immutable أو digest.
- جعل installer يرفض placeholder و`latest` في production ما لم يكن override صريحاً للطوارئ.
- توقيع الصور والتحقق من provenance/SBOM قبل النشر.

**معيار القبول**

- تثبيت نظيف على VM جديدة ينجح باستخدام version محدد، ثم health/readiness وsmoke test كامل.
- إعادة التثبيت بالنسخة نفسها تسحب digest نفسه.

---

## 5. أبرز الأشياء التي تعمل بشكل مختلف عن المتوقع

هذه ليست تحسينات نظرية؛ واجهة أو اسم أو إعداد يوحي بسلوك، لكن التنفيذ الحالي يفعل شيئاً آخر.

| المعرّف | المتوقع | السلوك الحالي | الأولوية |
|---|---|---|---|
| MF-01 | Streaming تدريجي من Hermes | التنفيذ يكتمل أولاً ثم يُقسّم الناتج إلى chunkين | P0 |
| MF-02 | المستخدم يبقى قادراً على الدخول بعد تفعيل Desktop | بعد 8 ساعات يحتاج مسار تفعيل/دعوة جديداً لعدم وجود refresh/login | P0 |
| MF-03 | Profile tool/approval policy تتحكم بالتنفيذ | Cowork يستخدم أدوات ثابتة ووضع موافقة يرسله العميل | P0 |
| MF-04 | الصور المرفقة تصل إلى Agent | تُخزن وتُعرض، لكن payload الخاص بـ Hermes لا يحتوي attachments وprompt لا يستخدمها | P1 |
| MF-05 | حد الصور متسق بين التطوير والإنتاج | الكود الافتراضي 8 MiB بينما env/installer يضبط WebSocket على 32 KiB | P1 |
| MF-06 | كل رسالة Telegram تكمل المحادثة نفسها | endpoint يمرر `conversation_id=None` فينشئ Session جديدة لكل رسالة | P1 |
| MF-07 | Telegram يخضع للحصص والمحاسبة | يستدعي AgentService مباشرة دون request quota أو token/cost recording الكامل | P1 |
| MF-08 | `rotate API key` ينشئ مفتاحاً بديلاً | endpoint يعطل القديم ويطلب من المدير إنشاء واحد جديد | P2 |
| MF-09 | `CELERY_BROKER_URL` يحدد broker | `app/celery_app.py:10-14` يستخدم `REDIS_URL` ويتجاهل الإعداد المعلن | P1 |
| MF-10 | تعديل Skill ينعكس على Profiles المرتبطة | skill يتغير في DB دون resync/version bump للـ profiles المتأثرة | P1 |
| MF-11 | إعادة sync تحفظ تعليمات Skills | بعض مسارات assignment/repair لا تمرر definitions، فتستبدلها placeholders عامة | P1 |
| MF-12 | `provider_key_id` في Profile يحدد المفتاح | resolver لا يعتمد الحقل كما توحي الواجهة وقد يختار مفتاحاً آخر | P1 |
| MF-13 | REST history ذو `limit` يعيد أحدث الرسائل | الاستعلام يرتب تصاعدياً ثم يطبق limit، فيعيد الأقدم في `app/api/chat.py:300-305` | P1 |
| MF-14 | `assistant_message_id` في WebSocket هو ID الرسالة المحفوظة | WS يولد UUID مستقلاً ويتجاهل ID الناتج من AgentService | P1 |
| MF-15 | روابط تفعيل الموظف تستخدم public origin الصحيح | fallback يبني `http://<host>:8001` بينما الإنتاج يعرض 80/443 | P1 |
| MF-16 | زر تحميل macOS يحمل نسخة موجودة | fallback يشير لمسار Mac بينما المستودع يحتوي installer Windows واحداً فقط | P2 |
| MF-17 | health تعني أن الخدمة قادرة على معالجة الطلب | health checks الأساسية ثابتة/سطحية ولا تختبر DB/Redis/Hermes | P1 |
| MF-18 | Cowork يُستخدم عند الحاجة إلى عمل داخل Workspace | أي Hermes profile مع Workspace يدخل Cowork حتى دون تحقق فعلي من النية | P1 |

---

## 6. Agent Runtime وCowork

### P1-01 — Timeouts غير متسقة وقد تترك أعمالاً معلقة

- API client الافتراضي 120 ثانية في `app/core/config.py:83`.
- orchestrator وruntime يستخدمان 300 ثانية في `app/hermes_orchestrator_app.py:31` و`app/local_hermes_runtime_app.py:529`.
- عملاء stream يستخدمون `httpx.AsyncClient(timeout=None)` في `app/services/hermes_orchestrator.py:77-98` و`app/hermes_orchestrator_app.py:313-333`.

قد يتوقف caller بعد 120 ثانية بينما يستمر Hermes حتى 300، أو يبقى stream عالقاً بلا نهاية. يجب تعريف budget واحد end-to-end: connect/read/idle/total، وتمرير deadline، وإلغاء العمل downstream عند انتهاء العميل.

### P1-02 — الصور غير موصولة بعقد Hermes

`AgentService` ينشئ محتوى multimodal للمسارات المباشرة، لكن `app/services/agent_runtime.py:44-77` لا يضع attachments في payload، واستدعاءات Hermes في `app/services/agent_service.py:479-490` و`687-698` لا تمررها، و`_build_prompt` في `app/local_hermes_runtime_app.py:163-225` يتجاهلها. كذلك يُعطّل Cowork عند وجود attachments في `app/api/websocket_chat.py:756-761`.

النتيجة هي نجاح ظاهري مع إجابة Agent لا ترى الصورة. المطلوب عقد attachment موحد، capability negotiation للـ model، ورفض واضح `unsupported_media` بدلاً من تجاهلها.

### P1-03 — التحقق من attachments غير كافٍ والتخزين داخل JSONB مكلف

الفحص في `app/services/agent_service.py:325-347` و`app/api/websocket_chat.py:173-193` يكتفي تقريباً بـ `data:image/` والطول. لا يوجد تحقق صارم من base64 أو magic bytes أو تطابق MIME أو decompression bomb. البيانات تُخزن base64 داخل JSONB في `app/models/message.py:16-17` وتعود مع history.

المطلوب رفع مباشر إلى object storage، فحص نوع/حجم/أبعاد/فيروسات، حفظ metadata وURL موقّع، وسياسة retention. كما يجب توحيد الحد: الكود 8 MiB في `app/core/config.py:63` مقابل 32 KiB في `.env.production.example` و`deploy/install.sh:172`.

### P1-04 — عدّ tokens/cost في Cowork أقل من الحقيقة

في `app/api/websocket_chat.py:417-420` يؤخذ `max()` عبر الخطوات بدلاً من جمع استهلاك كل step. الأمر نفسه يؤثر على total cost. هذا يقلل الحصة والفوترة في multi-step runs. يجب جمع usage لكل response مع منع double counting وتخزين usage per-step.

### P1-05 — Runs قد تبقى بحالة `running`

مسار step-limit ينهي run صراحة، لكن الاستثناءات الأخرى الخارجة من `_run_cowork_loop` قد تصل إلى caller دون تحويل AgentRun إلى failed. يجب وضع finalization في `try/except/finally` idempotent مع reason وtimestamps؛ ولا يجوز أن يبقى run غير نشط بحالة running أكثر من TTL مراقَب.

### P1-06 — انتظار موافقة العميل بلا timeout

`_wait_for_client_event` في `app/api/websocket_chat.py:283-307` ينتظر بلا مهلة. إغلاق غير نظيف أو عميل صامت يحجز coroutine وrun. يجب إضافة approval TTL، cancellation عند disconnect، وإنهاء run بحالة `approval_expired`.

### P1-07 — مزامنة Profiles غير ذرّية وقد تتلف النسخة العاملة

المزامنة تحذف artifacts الحية ثم تعيد كتابتها في `app/hermes_orchestrator_app.py:136-148` و`265-284`. فشل منتصف العملية يترك profile ناقصاً. يجب الكتابة إلى staging directory، التحقق من manifest/schema، ثم atomic rename مع الاحتفاظ بالنسخة السابقة للrollback.

كما أن delete يبني مساراً من ID في `app/hermes_orchestrator_app.py:287-296` دون فحص containment نهائي؛ حتى لو كانت المدخلات المعتادة موثوقة، يجب تثبيت boundary داخل الخدمة نفسها.

### P1-08 — Skills قد تصبح stale أو تُستبدل بمحتوى عام

- تعديل skill في `app/api/admin.py:390-429` لا يعيد مزامنة profiles المرتبطة.
- مسار assignment في `app/api/admin.py:625-650` ومسار repair قرب `1301-1306` يطلبان sync دون skill definitions.
- `app/services/hermes_profile_sync.py:38-59` يعوض التعريف المفقود بنص placeholder.

يجب بناء sync payload دائماً من snapshot كامل داخل transaction/version، مع dependency graph يرفع profile version عند تعديل skill، واختبار يثبت بقاء التعليمات الحقيقية بعد assign/repair.

### P2-01 — السجلات تطبع محتوى حساساً

`app/local_hermes_runtime_app.py:228-251` يطبع preview من prompt، و`app/api/websocket_chat.py:40-41` و`763-774` يطبع preview للرسائل. قد يتضمن ذلك بريد الموظف، أسرار كود، أو محتوى مشروع. الإنتاج يحتاج structured logging مع IDs وdurations فقط، redaction، ومستويات log مضبوطة دون raw prompts افتراضياً.

---

## 7. FastAPI، العزل، المصادقة، وTelegram

### P1-09 — Endpoint عام يستطيع إرسال رسائل من بوت Telegram

`GET /api/telegram/send/{chat_id}` في `app/api/telegram.py:185-193` لا يطلب مستخدماً أو admin/service secret. من يعرف chat ID يمكنه جعل البوت يرسل نصاً. يجب حذف endpoint العام أو جعله `POST` محمياً بصلاحية service/admin، مع audit وrate limit ومنع النص في query string.

### P1-10 — Telegram webhook قابل للتزوير عند غياب secret

التحقق من secret اختياري في `app/api/telegram.py:78-88`، والـ installer يتركه فارغاً في `deploy/install.sh:194-196`. في production يجب أن يكون webhook secret إلزامياً، مع فشل startup/readiness عند غيابه، والتحقق من header بالمقارنة الثابتة زمنياً.

### P1-11 — ربط Telegram قابل للاختطاف ولا توجد استمرارية أو محاسبة كاملة

- `/telegram/bind` يقبل chat ID يرسله المستخدم ويحذف ربط المالك السابق في `app/api/telegram.py:196-241`.
- الرسائل تمرر `conversation_id=None` في `app/api/telegram.py:165-172`.
- المسار لا يطبق نفس quota/metering/audit الموجود في REST/WS.

المطلوب challenge code يبدأ من الحساب ويُؤكد من داخل bot chat، منع نقل الربط دون موافقة/إبطال صريح، mapping ثابت إلى Session أو thread، وتمرير كل القنوات عبر application service واحد يطبق authorization/quota/metering.

### P1-12 — حد المعدل خلف reverse proxy قد يصبح مشتركاً بين كل المستخدمين

`app/main.py:89-109` و`131-171` يستخدم `request.client.host`. Nginx يرسل forwarded headers، لكن إعداد تشغيل Uvicorn لا يثبت trusted proxy chain. غالباً سترى API عنوان حاوية proxy لكل الطلبات، فيستهلك مستخدم واحد حصة IP للجميع.

يجب ضبط `--proxy-headers --forwarded-allow-ips=<proxy CIDR/IP>` بصورة ضيقة، وعدم الوثوق بـ X-Forwarded-For من الإنترنت، ثم اختبار عنوانين خارجيين فعلياً.

### P1-13 — “Account locked” لا يطابق التنفيذ

`_AUTH_LOCKOUT_THRESHOLD` معرّف في `app/main.py:123` لكنه غير مستخدم كقفل حساب مستمر. الرد في `145-150` و`163-168` يوحي بقفل حساب، بينما الموجود rate limit حسب IP/نافذة فقط. المطلوب فصل per-IP throttling عن per-account progressive delay/lock، وتسجيل الحدث دون تمكين account enumeration.

### P1-14 — JWT لوحة الإدارة محفوظ في localStorage و`window.name`

الخادم يضع cookie آمنة في `app/api/auth.py:97-107`، لكن `frontend/src/lib/api/client.ts:3-68` و`78-108` ينسخ token إلى localStorage و`window.name`. هذا يلغي فائدة HttpOnly ويزيد أثر XSS، و`window.name` قد يعيش عبر navigations.

استخدم HttpOnly Secure SameSite cookie فقط للـ Dashboard، أضف CSRF protection للعمليات المتغيرة، وافصل عقد Desktop token عن browser session. يجب ألا يصل JavaScript في المتصفح إلى access token.

### P1-15 — حدود المستأجر في AgentService ليست self-enforcing

`_ensure_session` يتحقق من الملكية في `app/services/agent_service.py:181-205`، لكن تحميل التاريخ لاحقاً يستخدم `conversation_id` الأصلي فقط في `437-451` و`626-640`. إذا استُدعيت الخدمة داخلياً بـ UUID لمستخدم آخر، تنشئ Session للطالب لكنها قد تحقن تاريخ UUID الأصلي في LLM. Admin test يستطيع تمرير conversation ID في `app/api/admin.py:691-700`.

يجب استخدام `session_obj.id` المتحقق منه حصراً، وربط كل query بـ user/tenant أو repository scoped. اختبارات isolation يجب أن تحاول UUID مستخدم آخر عبر كل entry point وتثبت عدم تسرب أي نص حتى إلى provider logs.

### P1-16 — رسائل الخطأ قد تكشف تفاصيل داخلية

بعض المسارات تعيد `str(exc)` مباشرة، مثل `app/api/chat.py:107-108` وأخطاء stream قرب `239-241`، إضافة إلى تفاصيل WS. قد تتسرب URLs داخلية أو provider response أو SQL details. المطلوب error code عام + correlation ID للعميل، والتفاصيل في سجل داخلي منقح فقط.

### P1-17 — تحقق LLM key عند startup لا ينسجم مع مفاتيح المنصة المخزنة

`app/core/config.py:39-42` يفرض env API key لمزودي OpenAI/Minimax في production، بينما `app/services/api_key_resolver.py` مصمم لاختيار مفتاح مشفر من DB. هذا قد يمنع startup رغم وجود platform key صحيح في DB، أو يجبر تكرار السر في env.

يجب اختيار مصدر حقيقة واحد: bootstrap secret محدود لمرة واحدة ثم DB/KMS، أو resolver-aware readiness بعد اتصال DB. لا تجعل Runtime يحصل على مفتاح control-plane عام.

### P2-02 — Profile provider key والعناصر nullable تحتاج عقد تحديث واضحاً

`provider_key_id` يُقبل في create/update دون تحقق مرجعي كافٍ، والـ resolver لا يستخدمه كاختيار حاسم. كذلك update لا يستطيع مسح حقول nullable لأن `None` يعني “لا تغيّر” في `app/api/admin.py:530-538`. استخدم `model_fields_set`/PATCH semantics، تحقق من الملكية/provider/scope، واجعل الواجهة تعرض المفتاح الفعلي المستخدم.

---

## 8. قاعدة البيانات، الحصص، القياس، والمهام الخلفية

### P1-18 — KPI اليومية بلا قيد uniqueness والتحديثات غير ذرّية

`app/models/kpi.py:10-23` لا يضع unique constraint على `(user_id, date)`. `_get_today_kpi` في `app/services/token_tracker.py:14-19` يفترض صفاً واحداً. طلبان متزامنان لأول مرة قد ينشئان صفين، وبعدها يفشل `scalar_one_or_none` أو تصبح الأرقام متفرقة.

أضف unique constraint، ونفذ atomic upsert. يلزم migration تنظف duplicates قبل إضافة القيد.

### P1-19 — فحص الحصة ثم الخصم غير ذري

`app/services/token_tracker.py:54-71` يفحص قبل التنفيذ ثم يحدث في `86-118`. طلبات متزامنة قد تمر كلها قبل تسجيل أي منها فتتجاوز الحد. حدود profile في `app/services/agent_service.py:227-261` تعتمد queries منفصلة، وتحسب output tokens فقط في موضع رغم أن واجهات أخرى تعرض total tokens.

المطلوب reservation ذري قبل run، ثم settle/release بعده، باستخدام row lock أو Redis Lua/DB transaction، مع تعريف موحد: requests، input، output، total، cost، timezone، وما يحدث للطلب الفاشل.

### P1-20 — WebSocket قد ينسب الاستهلاك إلى مزود/مفتاح خاطئ

`done_payload` في `app/api/websocket_chat.py:862-875` لا يحفظ provider المحلول، ثم القياس في `899-910` يعود إلى `settings.llm_provider`. إذا resolver اختار مزوداً آخر، قد تُحمّل الكلفة على مفتاح خاطئ أو لا تُسجل. يجب تمرير immutable execution snapshot: provider/model/key_id/pricing/version من لحظة resolution إلى run وusage record.

### P1-21 — Message ID المرسل عبر WS لا يطابق الرسالة المحفوظة

WS يولد UUID في `app/api/websocket_chat.py:827-830`، بينما AgentService ينشئ ويحفظ ID آخر في `app/services/agent_service.py:677` ويرسله في done الخاص به قرب `776-793`. WS يتجاهله ويعيد UUID غير موجود في DB. هذا يكسر reconciliation، feedback، retry، وربط الأحداث. يجب أن يكون التخزين هو مصدر ID الوحيد.

### P1-22 — إعداد Celery ومهام القياس غير متوافقة

- `CELERY_BROKER_URL` موجود في config، لكن `app/celery_app.py:10-14` يستخدم `settings.redis_url` للـ broker/backend.
- `track_token_usage` في `app/tasks.py:137-146` no-op.
- مهام التنظيف تستخدم cutoff timezone-aware مع أعمدة `DateTime` naive في `app/models/base.py:8`.
- الجدولة Asia/Riyadh لكن `date.today()` داخل الحاوية قد يكون UTC.

النتيجة إعداد مضلل، اختلاف يوم الحصة قرب منتصف الليل، واحتمال فشل مقارنة timestamps. اعتمد UTC-aware في التخزين، business timezone صريح للحصص، واختبارات حد اليوم/DST (حتى لو الرياض بلا DST حالياً)، وأزل/نفّذ المهام الوهمية.

### P1-23 — نجاح alert queue لا يعني نجاح الإرسال

مهمة البريد في `app/tasks.py:98-134` تلتقط الفشل وتعيد نصاً، ما يجعل Celery يعتبرها ناجحة، بينما evaluator يحدّث `last_notified_at` قرب `149-172` بعد queueing لا بعد delivery. قد تضيع إنذارات مع دخول cooldown.

استخدم retries/backoff وdead-letter/failed state، وحدّث delivered timestamp بعد نجاح SMTP، مع monitor مستقل لاختبار مسار التنبيه.

### P2-03 — الزمن والمال يحتاجان أنواعاً أدق

- timestamps في models غالباً timezone-naive.
- التكلفة تستخدم Float، لا Decimal/Numeric.
- لا توجد قيود DB كافية للقيم غير السالبة وبعض enums/statuses.

اعتمد `TIMESTAMPTZ` وUTC، و`NUMERIC` بدقة معرفة للعملة، وcheck constraints. نفذ migration مع backfill واختبارات rounding، دون تغيير واجهة التصميم.

---

## 9. Dashboard وواجهات الإدارة

### P1-24 — رابط التفعيل المنشأ للموظف خاطئ في نشر Compose المعتاد

`frontend/src/app/employees/page.tsx:111-128` يرفض hostname الداخلي `api` ثم يبني fallback على `http://<public-host>:8001`. إعداد Compose يمرر `NEXT_PUBLIC_API_URL` فقط ولا يضمن public origin/download URLs. الإنتاج عادة يعرض 80/443، لذلك الرابط غير آمن أو غير قابل للوصول.

الحل هو متغير canonical public URL إلزامي مثل `PUBLIC_APP_ORIGIN=https://agents.example.com` يُستخدم server-side لإنشاء الرابط، لا استنتاج origin داخل browser. اختبار القبول يجب أن يفتح الرابط من جهاز خارج الشبكة.

### P1-25 — Endpoint الإحصاءات ينفذ عدداً كبيراً من الاستعلامات المتسلسلة

مسار stats في `app/api/admin.py:1625-1992` ينفذ عشرات round trips، منها loops يومية وطلب Hermes شبكي. مع نمو البيانات ستصبح لوحة الإدارة بطيئة وقد تعلق بسبب runtime.

استخدم aggregate queries/CTEs، cache قصير، وافصل runtime health عن إحصاءات DB مع timeouts. ضع SLO للـ admin API وراقب query count/latency.

### P1-26 — Presence داخل ذاكرة process واحدة

`app/services/presence_service.py` يحتفظ بالحضور في الذاكرة. عند تشغيل أكثر من API worker/replica سترى كل نسخة جزءاً من المستخدمين. انقل presence إلى Redis مع TTL/heartbeats، أو صرح بأن API single-replica إلى أن يتم ذلك.

### P2-04 — عمليات Admin لا تحول تعارضات DB إلى أخطاء عقد واضحة

أمثلة: duplicate assignment أو duplicate profile name قد تنتهي 500، وبعض date filters تستخدم `datetime.fromisoformat` دون تحويل ValueError إلى 422. المطلوب mapping ثابت: 409 للتعارض، 422 للمدخل غير الصالح، وعدم كشف SQL details.

### P2-05 — رابط macOS الافتراضي غير مضمون

صفحة الموظفين في `frontend/src/app/employees/page.tsx:50-65` و`392-402` تعرض fallback لنظام macOS، لكن المتتبع محلياً installer Windows واحد فقط تحت `frontend/public/downloads`. يجب أن تأتي download manifest من release service وتعرض فقط artifacts الموجودة والموقعة والمتوافقة مع version الحالي.

---

## 10. Desktop Application

### P1-27 — Offline queue قد يرسل الرسالة إلى المحادثة الخطأ

`desktop/src/renderer/scripts/01-state-and-i18n.js:520-548` يخزن الرسالة وattachments، لكنه لا يثبت conversation/project/workspace context، ثم flush يستخدم الحالة الحالية عبر `desktop/src/renderer/scripts/04-ui-overrides.js:467-480`. كذلك تُحذف الرسالة من queue بمجرد `WebSocket.send` دون server acknowledgement أو idempotency key.

سيناريو واضح: يرسل المستخدم في Project A وهو offline، ينتقل إلى Project B، ثم يعود الاتصال؛ تصل الرسالة إلى B وقد تختفي محلياً إن انقطع الاتصال بعد send وقبل commit.

المطلوب queue item immutable يحوي tenant/user/conversation/workspace/profile/client_message_id، وتأكيد server persisted ACK، وإعادة آمنة idempotent مع ترتيب وحد concurrency واحد لكل conversation. attachments الحساسة لا تحفظ base64 نصاً واضحاً في electron-store.

### P1-28 — بروتوكول activation يقبل API origin يختاره الرابط

`desktop/src/main/main.js:74-101` يسمح لـ `fqsaas://activate` بحمل `http` أو `https` origin. رابط خبيث يمكنه توجيه التطبيق إلى خادم مهاجم وتسليم token/بيانات دخول أو جعل المستخدم يعمل ضد منصة مزيفة.

يجب تثبيت allowlist origins موقعة داخل الإصدار، فرض HTTPS في production، وإما توقيع activation payload من الخادم أو استخدام code قصير يُستبدل عبر origin المعروف. لا يُخزن activation token الخام بعد نجاح exchange.

### P1-29 — التخزين الآمن يهبط إلى plaintext

`desktop/src/main/main.js:22-57` يستخدم fallback plaintext عندما لا تتوفر `safeStorage`، ثم قد يعيد token إلى renderer في `724-738`. يجب أن يفشل تخزين الجلسة بأمان أو يستخدم OS credential vault بديل، وألا يمرر refresh credential إلى renderer. renderer يحتاج API محدوداً لاستخراج جلسة خام.

### P1-30 — عمليات الملفات غير ذرّية وقد تترك المشروع نصف مطبق

المعاينة ثم apply في `desktop/src/main/main.js:600-679` و`873-885` تشمل عمليات متعددة بلا transaction/rollback، وبعض الكتابات لا تضمن إنشاء الأب. فشل العملية رقم 3 يترك أول عمليتين مطبقتين. استخدم staging + atomic rename قدر الإمكان، journal للعملية، preconditions/hash، rollback plan، ونسخة احتياطية محدودة قبل destructive apply.

### P1-31 — فحص Workspace متزامن داخل Electron main process

المسح والقراءة recursive في `desktop/src/main/main.js:382-426` و`548-579` يحدثان في main process بلا حدود ملفات/عمق واضحة. مستودع كبير أو symlink loop/ملفات ضخمة قد يجمد UI. انقل العمل إلى worker، أضف ignore rules وحصصاً وحدوداً، وأرسل progress/cancellation.

### P1-32 — Auto updater يثبت فور التحميل

`desktop/src/main/main.js:231-235` يستدعي quit/install عند download. قد يفقد المستخدم تعديلات editor أو preview غير مطبق. المطلوب prompt واضح، فحص dirty state، اختيار “الآن/عند الإغلاق”، واسترجاع الجلسة بعد التحديث. هذا تغيير سلوكي فقط وليس تغيير تصميم.

### P2-06 — Preview tokens ضعيفة وغير مرتبطة بحالة الملف

tokens في مسار المعاينة مبنية على `Math.random` ولا TTL/one-time binding قوي. اربط approval بـ cryptographic nonce وhash للعمليات والمحتوى وworkspace/user/run، ثم ارفض apply إذا تغير أي ملف منذ preview.

### P2-07 — CSP واسعة بالنسبة لتطبيق Desktop

CSP تسمح `connect-src http` و`script-src 'unsafe-inline'` في `desktop/src/main/main.js:174-184`. بعد تثبيت origins يجب حصر الاتصال بـ HTTPS/WSS المعتمدين وإزالة inline scripts تدريجياً. هذه توصية أمنية ولا تستلزم تغيير الشكل.

---

## 11. النشر، الصحة، النسخ الاحتياطي، وسلسلة التوريد

### P1-33 — Health checks سطحية وتعلن الأخضر أثناء عطل حقيقي

- `/api/status` في `app/main.py:185-193` يعيد healthy دون فحص dependencies.
- Compose يستخدمه لفحص API بدلاً من `/api/ready`.
- `/healthz` للـ orchestrator في `app/hermes_orchestrator_app.py:151-153` لا يفحص runtime.
- `/health` للـ Runtime في `app/local_hermes_runtime_app.py:34-36` لا يفحص Hermes binary أو profile storage/provider.
- `/api/ready` أفضل، لكنه ينشئ engine وRedis client جديدين لكل call في `app/api/health.py:11-33`.

افصل liveness عن readiness وعن startup، واجعل readiness تختبر pool الحالي وRedis وHermes بمهلة قصيرة دون استدعاء LLM مدفوع. Compose/load balancer يجب أن يوجها traffic بناء على readiness، لا liveness.

### P1-34 — كل الخدمات تحصل على `.env.production`

API وfrontend/worker/beat/orchestrator/runtime تستخدم env file واسعاً في Compose. حتى دون P0-02، هذا يخالف least privilege ويضخم blast radius. أنشئ env/secrets منفصلة لكل service، واستخدم Docker/Kubernetes secrets أو secret manager، ولا تضع أسرار البناء في frontend image.

### P1-35 — صور وDependencies غير مثبتة بما يكفي

- `hermes-agent` غير مثبت على إصدار محدد في `requirements.txt`.
- صور base mutable، وإصدارات release تستخدم `latest`.
- `docker-compose.production.yml` يبني hermes-runtime من build context العام ولا يضمن استخدام `Dockerfile.hermes-runtime` المتخصص.

ثبت dependencies مع lock/hashes، الصور بـ digest، افحص CVEs، ولّد SBOM ووقع artifacts. اختبر أن binary/version المتوقع موجود قبل readiness.

### P1-36 — النسخة الاحتياطية تجمع الأسرار plaintext مع البيانات

`deploy/backup.sh:19-26` ينسخ `.env.production` كاملة إلى مجلد backup على المضيف مع dump والprofiles. هذا يجعل نسخة واحدة كافية لاختراق كل شيء. checksum بجانب الملفات يكشف فساداً عرضياً فقط ولا يمنع مهاجماً يغيّر الملف والـ checksum معاً.

استخدم تشفيراً مستقلاً بمفتاح خارج الخادم، صلاحيات ضيقة، offsite/immutable retention، ولا تنسخ الأسرار أو خزّن مراجع secret manager. نفذ restore drill دوري مع RPO/RTO مسجلين.

### P1-37 — Restore مسار تدميري دون ضمان رجوع الخدمة

`deploy/restore.sh:26-34` يوقف الخدمات ويمحو/يعيد البيانات؛ إذا فشل منتصف الطريق قد تبقى المنصة متوقفة أو DB جزئية. المطلوب pre-restore snapshot، تحقق checksum/signature، restore إلى DB مؤقتة، اختبارات schema/smoke، ثم cutover ذري، مع trap يعيد حالة آمنة.

### P1-38 — لا توجد CI شاملة للمكوّنات الثلاثة

الموجود أساساً workflow لإصدار macOS Desktop. لا توجد بوابة موحدة للـ backend tests، migration graph، frontend lint/build، Windows Desktop، Docker smoke/e2e، secret scan، dependency/image scan، أو integration contracts.

هذا مهم لأن عدة عيوب أعلاه—رأسا Alembic، رابط التفعيل، وعقد message IDs—يمكن منعها آلياً قبل الدمج.

### P2-08 — تشغيل migration داخل أمر بدء API لا يناسب replicas

تشغيل `alembic upgrade head` من كل instance يسبب race عند التوسع، ويخلط فشل schema مع app rollout. استخدم job وحيد قبل deployment، مع backward-compatible expand/migrate/contract وrollback plan.

### P2-09 — لا توجد حدود موارد وسياسات container كافية

أضف CPU/RAM/PID limits، log rotation، read-only filesystem حيث يمكن، capability drop، non-root، restart budgets، وdisk alerts. Agent workloads تحديداً تحتاج per-run quotas لمنع noisy neighbor.

---

## 12. تحسينات Production مهمة بعد إغلاق العيوب

هذه تحسينات ذات قيمة تشغيلية مباشرة، وليست تغييرات تصميم:

### 12.1 توحيد مسار تنفيذ الرسالة

حالياً REST وWS وTelegram وAdmin test وCowork لا تمر كلها عبر نفس سلسلة السياسات. ينبغي وجود application service واحد ينفذ بالترتيب:

1. authenticate + tenant/session authorization.
2. idempotency وإثبات ownership.
3. quota reservation.
4. profile/provider/tool policy snapshot.
5. تنفيذ Runtime مع deadline/cancellation.
6. حفظ الرسالة والusage بصورة ذرية أو عبر outbox.
7. settlement للحصة والكلفة.
8. audit/telemetry ثم ACK.

هذا يمنع أن تكون قناة Telegram أو Cowork استثناءً يتجاوز القياس أو الحوكمة.

### 12.2 Outbox/Inbox للأحداث المهمة

استخدم transactional outbox لأحداث usage/audit/notifications، وconsumer idempotent. لا تعتمد على “تمت إضافته إلى Celery” كدليل أن التنبيه أو القياس تم فعلياً.

### 12.3 Observability قابلة للتشخيص

أضف OpenTelemetry traces عبر Desktop request ID → FastAPI → orchestrator → runtime → provider، مع metrics مثل:

- request/run success rate حسب القناة والمزود/profile.
- queue wait، time-to-first-token، total latency.
- active/queued/cancelled/stuck runs.
- quota reservations vs settlements.
- DB pool وRedis/Celery lag.
- WebSocket disconnect/reconnect/offline replay.
- tool approval requested/approved/denied/expired.

لا تسجل raw prompts أو tokens أو file contents. عرّف retention وصلاحيات الوصول للسجلات.

### 12.4 نمط توسع معلن

قبل إضافة replicas:

- انقل presence والحالة المشتركة إلى Redis/DB.
- اجعل WebSocket قابلاً للتوجيه أو استخدم broker/pub-sub.
- اجعل Runtime queue-aware مع fairness لكل tenant.
- افصل migrations وbeat singleton.
- اختبر graceful shutdown وتصريف WebSockets/runs.

### 12.5 سياسة بيانات واحتفاظ

حدد مدة الاحتفاظ بالرسائل، attachments، prompts، runs، audit، وbackups. أضف حذفاً قابلاً للإثبات وexport، وامنع تخزين attachment base64 إلى ما لا نهاية. Audit يحتاج append-only أو صلاحيات DB تمنع API role من update/delete.

---

## 13. خطة إصلاح مرتبة

### المرحلة 0 — احتواء فوري للأسرار (نفس اليوم)

1. تدوير Supabase keys التاريخية وفحص سجلات استخدامها.
2. منع push إضافي للملفات التاريخية/بيانات PostgreSQL.
3. أخذ نسخة مرجعية آمنة، ثم تخطيط تنظيف Git history وإبلاغ كل المستنسخين.
4. تقييد وصول Runtime للأسرار والشبكة مؤقتاً حتى تنفيذ العزل الكامل.

### المرحلة 1 — موانع الإصدار (2–5 أيام عمل)

1. إصلاح Alembic heads وإضافة migration CI.
2. تصميم access/refresh/device session لـ Desktop وإزالة WS-token fallback.
3. فرض tool/approval policy server-side.
4. إصلاح symlink containment في Desktop.
5. تحويل Hermes subprocess إلى async/worker وبث حقيقي مع cancellation.
6. إصلاح صور release والـ installer إلى version/digest حقيقيين.

### المرحلة 2 — سلامة الوظائف والبيانات (أسبوع تقريباً)

1. توحيد الرسالة بين REST/WS/Telegram/Cowork.
2. توصيل attachments فعلياً أو رفضها بوضوح، ونقلها إلى object storage.
3. إصلاح KPI uniqueness والحصص الذرية والـ provider/message usage identity.
4. إصلاح skill/profile sync وprovider key contract.
5. إصلاح Telegram auth/binding/session/metering.
6. إصلاح offline queue وatomic file apply.

### المرحلة 3 — التشغيل والاعتمادية (أسبوع إلى أسبوعين)

1. readiness حقيقية وtimeouts/deadlines موحدة.
2. CI/CD كاملة واختبارات عقد وأمن.
3. نسخ احتياطي مشفر وrestore drill.
4. observability/SLOs وتنبيهات delivery-tested.
5. container hardening وdependency/image pinning.
6. load/soak/chaos tests قبل قرار Go-Live.

---

## 14. بوابات القبول قبل الإنتاج

لا يكفي إغلاق التذاكر برمجياً؛ أوصي بعدم تحويل القرار إلى Go إلا بعد اجتياز هذه البوابات:

### الأمن والعزل

- secret scan كامل لتاريخ Git والصور وartifacts ينجح.
- prompt-injection test لا يصل إلى env/control-plane/شبكة غير مصرح بها.
- tenant isolation suite يغطي REST/WS/Telegram/Admin test وكل UUID قابل للإدخال.
- tool policy negative tests تثبت أن العميل لا يوسع صلاحياته.
- Desktop symlink/junction escape tests تنجح على Windows وmacOS.

### البيانات والهجرات

- Alembic رأس واحد.
- upgrade من schema الإصدار السابق وfresh install ينجحان.
- quota concurrency test لا يتجاوز الحد عند 50 طلباً متزامناً.
- usage/cost reconciliation يطابق provider responses في single-step وmulti-step.
- backup restore إلى بيئة فارغة يحقق RPO/RTO ويجتاز smoke tests.

### الوظائف

- جلسة Desktop تتجدد بعد انتهاء access token دون دعوة جديدة.
- offline replay يبقى في المحادثة الأصلية ولا يكرر الرسالة.
- صورة ناجحة يراها model فعلياً؛ والنوع غير المدعوم يعطي خطأ صريحاً.
- streaming يحقق time-to-first-token قبل انتهاء run.
- تعديل skill يظهر في runtime version الجديدة ولا يستبدل التعليمات.
- Telegram يحافظ على thread ويطبق الحصة والقياس نفسها.

### الاعتمادية

- load test بعدد المستخدمين المتوقع × 2 لمدة ساعتين مع SLO معلن.
- قطع Redis/DB/Runtime/provider يسبب readiness/خطأ مضبوطاً، لا healthy كاذبة أو hang.
- graceful restart لا يفقد رسائل أو يترك runs دائمة.
- queue backpressure يمنع مستخدماً واحداً من استنزاف Runtime.
- alert delivery failure يولد تنبيهاً ثانوياً قابلاً للرؤية.

### سلسلة الإصدار

- Backend lint/type/tests، frontend lint/build، Desktop checks/build/signing، migrations، Docker smoke، SAST/secret/dependency/image scans كلها إلزامية في CI.
- Desktop Windows/macOS artifacts موقعة، update manifest موقّع، وروابط التحميل مأخوذة من manifest حقيقي.
- صور الحاويات مثبّتة digest وموقعة ولها SBOM.

---

## 15. نتائج الفحوص المنفذة أثناء المراجعة

| الفحص | النتيجة | الملاحظة |
|---|---|---|
| `py -m compileall -q app migrations scripts` | نجح | لا توجد أخطاء Python syntax في الملفات المفحوصة |
| `npm run lint` للـ frontend | نجح مع تحذير واحد | تحذير dependencies لـ React Hook في `frontend/src/app/agent-runtime/page.tsx:70`، غير مانع وحده |
| `npm run build` للـ frontend | نجح | Next.js production build وTypeScript وstatic generation نجحت |
| `node --check` لملفات Desktop JS | نجح | لا توجد أخطاء syntax |
| `npm run release:check` للـ Desktop | فشل كما هو متوقع | `UPDATE_FEED_URL` والتوقيع غير مضبوطين وrelease API ما زال localhost في بيئة المراجعة |
| `py -m pytest -q` | لم يُنفذ | `pytest` غير مثبت في Python المتاح؛ هذا قيد بيئة مراجعة وليس فشل test |
| Docker Compose config | لم يكتمل | `.env.production` غير موجودة وDocker config للمستخدم غير متاحة ضمن بيئة المراجعة |
| فحص migration graph ساكن | كشف مانعاً | الترحيلان الجديدان يشتركان في الأب نفسه ويشكلان رأسي Alembic |
| فحص Git tracked files | كشف مانعاً | ملفات env تاريخية، قيم Supabase تبدو حقيقية، و2,769 ملف PostgreSQL مؤقتاً متتبعة |

لا تعني نجاحات البناء أن المنصة اجتازت integration/load/security tests؛ تلك الاختبارات غير موجودة أو غير قابلة للتشغيل الكامل في البيئة الحالية، ولهذا أدرجت كبوابات إلزامية.

---

## 16. القرار النهائي

المنصة **قوية وظيفياً كأساس**، ولا تحتاج تغيير تصميم أو إعادة بناء شاملة. المطلوب هو تقوية boundaries والعقود التشغيلية المحيطة بما يعمل حالياً.

أوصي بالترتيب التالي دون تفاوض على الأولويات:

1. احتواء الأسرار وتنظيف Git.
2. عزل Runtime وفرض سياسات الأدوات.
3. إصلاح دورة جلسة Desktop وsymlink boundary.
4. إصلاح migrations والتزامن والقياس.
5. إصلاح العقود التي تعطي نجاحاً كاذباً: streaming، الصور، links، IDs، وskill sync.
6. إكمال CI/readiness/backup restore/load tests.

بعد إغلاق `P0` واجتياز بوابات الأمن والهجرات والجلسة والـ streaming، يمكن إعادة التقييم إلى **Go مشروط**. وبعد إغلاق عناصر `P1` الحرجة واجتياز load/restore/failure tests، يصبح قرار **Production Go** مهنياً وقابلاً للدفاع عنه.
