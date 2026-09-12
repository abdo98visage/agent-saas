# تقرير تنفيذ المرحلة الرابعة: UAT حي متعدد المستخدمين

**التاريخ:** 2026-08-04  
**البيئة:** Docker E2E محلية مطابقة لتوزيعة المنصة، Dashboard فعلي، FastAPI، PostgreSQL، Redis، Worker، Beat، Hermes Orchestrator، Hermes Runtime، ونسخة Windows Desktop معبأة.  
**القرار:** **PASS للمرحلة الرابعة** والانتقال إلى المرحلة الخامسة: حقن الأعطال والتعافي.

## النطاق المنفذ

- تشغيل أربع نسخ Desktop مرئية ومستقلة بأدلة AppData وWorkspace ومنافذ CDP منفصلة.
- شخصيات Accounting وMarketing وHR وIT بحسابات وProfiles ومحادثات منفصلة.
- إبقاء Dashboard مفتوحاً والتحقق المرئي من `المستخدمون المتصلون (4)` والنشاطات الناتجة عن الاختبار.
- استخدام فعلي للموديل وHermes Runtime، وليس mock أو HTTP health فقط.
- تشغيل 150 دقيقة متصلة، برسالة متزامنة لكل مستخدم كل ثلاث دقائق، ثم burst متواصل في نهاية الاختبار.
- تغيير Knowledge وإلغاء MCP والمستخدمون متصلون.
- انقطاع HR لمدة دقيقتين، وإعادة تحميل Marketing، وتعطيل HR وإعادة تفعيله.

## النتيجة الرقمية

| المقياس | النتيجة |
|---|---:|
| مدة التشغيل | 150 دقيقة |
| الدورات | 61 |
| الردود الدورية الصحيحة | 244 / 244 |
| رسائل كل مستخدم | 61 user + 61 assistant |
| client message IDs الفريدة لكل مستخدم | 61 / 61 |
| duplicate client IDs | 0 |
| فشل UAT النهائي | 0 |

| المستخدم | p50 | p95 | الحد الأقصى |
|---|---:|---:|---:|
| Accounting | 9.099s | 15.184s | 15.758s |
| Marketing | 9.183s | 14.484s | 16.287s |
| HR | 11.018s | 15.103s | 16.003s |
| IT | 12.102s | 16.088s | 17.077s |

لم يظهر تدهور متزايد مع الزمن. وفي burst النهائي بقيت الردود ضمن المجال نفسه تقريباً.

## السيناريوهات الحية المقبولة

- تجاوز الجولة 13 التي كانت تكشف خطأ quota القديم، مع نجاح IT بلا `Daily token quota exceeded`.
- إضافة Knowledge جديدة لـAccounting أثناء اتصال Desktop، ثم استرجاع الرمز الجديد مع citation `[K1]`.
- إلغاء MCP عن IT أثناء الجلسة، وتحديث قائمة Desktop، مع استمرار المحادثة العادية.
- إعادة تحميل Marketing، واستعادة Conversation نفسها، ثم الحصول على `REOPENED-OK`.
- قطع HR لمدة دقيقتين، حفظ رسالة واحدة محلياً، ثم إرسالها بعد العودة مع `persisted_count=1`.
- تعطيل HR من الإدارة، رفض الرسالة، إعادة التفعيل وتسجيل الدخول، ثم الحصول على `REACTIVATED-OK`.
- اختبار MCP حقيقي سابق للمرحلة: approval من واجهة Desktop واستدعاء Context7 بنجاح.
- اختبار محادثة Desktop من 30 دورة واستعادة marker قديم بعد تجاوز نافذة الرسائل القصيرة.

## العيوب المؤثرة التي ظهرت وأُغلقت

### 1. quota قديمة داخل WebSocket مفتوح

كان تعديل quota من الإدارة لا ينعكس على اتصال WebSocket الموجود حتى يعيد المستخدم الاتصال. تم تحديث سياسة المستخدم من قاعدة البيانات قبل كل رسالة، مع إغلاق الاتصال عند التعطيل أو تغيير token version. اجتاز الإصلاح اختبارات الوحدة والجولة الحية 13 وما بعدها.

### 2. عبور رسالة مرفوضة إلى جلسة جديدة

كشفت مراجعة قاعدة البيانات أن رسالة `SHOULD-NOT-RUN` المرسلة أثناء تعطيل HR حُفظت في offline queue ثم نُفذت بعد إعادة التفعيل. تم إصلاح Desktop بحيث:

- يعامل server error غير القابل لإعادة المحاولة كفشل مصادقة قبل enqueue.
- يمسح queue عند عبور حد المصادقة فقط.
- لا يعيد flush إدخال العناصر بعد auth failure.
- يحافظ على queue في انقطاع الشبكة العادي.

أعيد بناء النسخة المعبأة واختبارها حياً. النتيجة النهائية: رفض خلال أقل من ثانية، queue تساوي صفراً، و`forbidden_message_count=0` في PostgreSQL بعد إعادة التفعيل.

### 3. build script لا يعمل بصورة موثوقة على Windows

كان `electron-builder --config electron-builder.js` يُفسر محلياً كفتح ملف الإعداد في VS Code بسبب اقتران امتداد `.js`. تم استدعاء CLI بواسطة Node صراحةً في scripts الأربعة. نجح بناء `win-unpacked` وNSIS installer بعد الإصلاح.

### 4. تحديث Task Schedule يعيد HTTP 500

أعاد تعطيل schedule تجريبية خطأ `MissingGreenlet` عند قراءة `updated_at` المنتهي الصلاحية بعد flush. أضيف `db.refresh(schedule)` قبل تكوين الاستجابة، وأضيف regression test. نجح HTTP PUT وأصبحت schedule `enabled=false` و`next_run_at=null`.

### 5. تشخيص UAT عند خروج Desktop

تم تحسين أدوات الاختبار كي ترفض أوامر CDP فور إغلاق الاتصال، وتراقب خروج Electron بدل انتظار مؤقت طويل، وتستخدم مهلة مناسبة لازدحام تهيئة أربعة مستخدمين. هذه تغييرات أدوات اختبار فقط.

## الاختبارات بعد الإصلاح

- Backend targeted regression: `39 passed`.
- Backend full suite النهائي: `80 passed`.
- Desktop test suite: `1 passed`.
- فحص syntax لملفات renderer ومشغّل UAT: ناجح.
- Windows packaged build وNSIS installer: ناجحان.
- جميع خدمات Docker: تعمل؛ الخدمات التي تملك healthcheck حالتها healthy.
- لم يظهر Traceback خلال التشغيل النهائي. مهمة `Hourly durable validation` القديمة كانت بيانات UAT من جولة سابقة، وتم تعطيلها عبر API بعد إصلاح endpoint.

## الأدلة

- `uat-evidence/live-desktop-uat-final2.jsonl`: دليل التشغيل الكامل 150 دقيقة.
- `uat-evidence/desktop-auth-queue-regression-final.jsonl`: دليل إغلاق ثغرة عبور الرسالة بعد إعادة التفعيل.
- `uat-evidence/live-desktop-uat.jsonl` وملفات retry: محفوظة كأدلة فشل قبل الإصلاح.

## القيود وما لم يُعتمد بعد

- هذه المرحلة تثبت UAT حياً لمدة 150 دقيقة، ولا تستبدل soak البنية لمدة 12–24 ساعة في المرحلة السابعة.
- أرقام السعة التجارية لا تعتمد بعد؛ يجب إكمال fault injection، session longevity، soak، capacity، upgrade وrestore.
- تنبيهات usage threshold في Dashboard ناتجة عن حسابات UAT ذات الاستهلاك المتعمد، وليست انقطاع خدمة.

## بوابة الانتقال

لا يوجد عيب S0/S1 مفتوح من سيناريوهات المرحلة الرابعة. يسمح بالانتقال إلى **المرحلة الخامسة: Failure Injection**، مع إبقاء قرار Production النهائي مؤجلاً حتى إكمال بقية المراحل.
