# تقرير تنفيذ المرحلة السادسة — انتهاء الجلسة والاستمرار الطويل

**التاريخ:** 2026-08-04  
**البيئة:** API بمدة access مؤقتة دقيقتين، أربع نسخ Desktop packaged ظاهرة، ثم إعادة baseline إلى 480 دقيقة  
**القرار:** **PASS — الانتقال إلى المرحلة السابعة**

## 1. الخلاصة

نُفذت اختبارات انتهاء access token ودوران refresh token وإعادة WebSocket وفتح Desktop والإبطال الإداري على أربع جلسات موظفين مستقلة. لم يُطلب من المستخدم الطبيعي إعادة التفعيل عند انتهاء access token، ولم يتأثر أي مستخدم بإبطال جلسة مستخدم آخر.

بعد الاختبار أُعيد إعداد API إلى `ACCESS_TOKEN_EXPIRE_MINUTES=480`، ودُورت جلسات المستخدمين الأربعة فعلياً إلى توكنات صلاحيتها `28800` ثانية مع بقاء refresh session محفوظة.

## 2. النتائج المنفذة

| الحالة | النتيجة |
|---|---|
| انتهاء access token الطبيعي بعد دقيقتين | PASS |
| REST request بعد الانتهاء | PASS — refresh ثم retry تلقائي |
| طلبان حصلا على 401 في الوقت نفسه | PASS — كلاهما نجح ودوران واحد فقط |
| إغلاق وإعادة WebSocket بعد انتهاء access | PASS |
| إعادة فتح Desktop packaged بعد انتهاء access | PASS |
| ثلاث refresh rotations متتابعة | PASS |
| replay لتوكن refresh مستعمل | PASS — HTTP 401 |
| refresh token منتهي فعلياً في DB | PASS — HTTP 401 |
| إبطال جلسة HR من المدير | PASS — Desktop انتقل إلى authRequired |
| عزل الإبطال عن المستخدمين الآخرين | PASS |
| إعادة تفعيل HR بعد الإبطال | PASS |

## 3. اختبار المستخدمين الأربعة

وُزعت السيناريوهات بعد انتهاء نفس نافذة الدقيقتين طبيعياً:

- **Accounting:** نفذ `GET /auth/me`، استقبل 401، دوّر refresh، ثم أعاد الطلب بنجاح.
- **Marketing:** نفذ `/auth/me` و`/auth/assigned-profiles` بالتزامن بعد الانتهاء. نجح الطلبان، وأثبت فحص `auth_sessions` إنشاء جلسة جديدة واحدة فقط عند `2026-08-04 15:55:55.215783`.
- **HR:** أُغلق WebSocket ثم أُعيد فتحه. جلب Desktop ticket جديداً بعد refresh وعاد الاتصال OPEN.
- **IT:** أُعيد تحميل برنامج Desktop packaged بتوكن منتهٍ. بقي المستخدم مسجلاً، دُوّر التوكن، وعاد WebSocket OPEN دون activation.

ثم نفذ Accounting ثلاث rotations متتابعة؛ كانت expiries مختلفة وأصبحت refresh tokens السابقة غير قابلة لإعادة الاستخدام.

## 4. العيوب المكتشفة والإصلاحات

### 4.1 WebSocket كان ينتظر تهيئة ثانوية بعد refresh عند فتح Desktop

**المشكلة:** عند إعادة فتح Desktop بتوكن منتهٍ، نجح refresh واستُعيد `currentUser`، لكن bootstrap كان ينتظر تحميل assigned profiles وMCP وworkspace files قبل بدء WebSocket. تأخر مكوّن ثانوي كان يترك chat offline رغم سلامة الجلسة.

**الإصلاح:** يبدأ `connectWebSocket()` مباشرة بعد نجاح `loadCurrentUser()`، قبل التهيئة الاختيارية اللاحقة. لم يتغير التصميم أو أي وظيفة أساسية.

**التحقق:** بُني executable packaged جديد، وشُغل مرئياً بنفس user-data، ثم أُعيد اختباره بعد انتهاء access. عاد `currentUser=true` و`authRequired=false` و`WebSocket.OPEN` فوراً.

### 4.2 heartbeat كان يتجاوز فحص الإبطال الإداري

**المشكلة:** WebSocket كان يعيد تحميل `token_version` قبل رسائل المستخدم فقط، بينما يجيب على ping/heartbeat أولاً. لذلك يمكن أن يبقى المستخدم المبطل ظاهراً online إلى أن يرسل رسالة فعلية.

**الإصلاح:** أصبح `refresh_websocket_user()` وفحص active/token_version يسبقان ping وheartbeat وأي رسالة أخرى. عند الإبطال يرسل الخادم خطأ non-retryable ويغلق WebSocket بالكود `4001`.

**التحقق الحي:** بعد توليد Desktop invite جديد لـHR ارتفع `token_version` وتعطّل الحساب. heartbeat التالي أغلق الجلسة وأظهر `authRequired=true`. بقي Accounting وMarketing وIT على `WebSocket.OPEN` واستطاعوا استدعاء `/auth/me`. بعد ذلك أُعيد تفعيل HR وعاد متصلاً.

## 5. سلامة دوران refresh

المسار الخادمي يستخدم:

- hash لـrefresh token في قاعدة البيانات، وليس القيمة الخام.
- `SELECT ... FOR UPDATE` لمنع سباق الدوران.
- إبطال الجلسة القديمة قبل إصدار الزوج الجديد.
- مطابقة `token_version` مع المستخدم.
- رفض الجلسة المعطلة أو غير المفعلة أو المنتهية.

التحقق العملي:

1. login من نوع desktop أعطى refresh أولاً.
2. استخدامه مرة واحدة أعطى زوجاً جديداً.
3. إعادة استخدام القديم أعادت `401 Invalid or expired refresh token`.
4. جرى تعديل `expires_at` للجلسة الجديدة التجريبية إلى الماضي.
5. استخدامها أعاد نفس 401.

لم تُمس جلسات Desktop الأربع في اختبار expiry الخادمي؛ استُخدمت جلسة دخول إضافية مستقلة.

## 6. أدلة التنفيذ

- `uat-evidence/session-expiry-four-desktops-live-final.jsonl`: انتهاء طبيعي، REST refresh، concurrent 401، WebSocket refresh، Desktop reopen، وثلاث rotations.
- `uat-evidence/session-admin-revoke-live.jsonl`: إبطال HR وعزل المستخدمين وإعادة التفعيل.
- `uat-evidence/refresh-replay-expiry-live.jsonl`: replay وexpiry وsingle rotation.
- `uat-evidence/docker-compose.phase6.yml`: override الاختبار المؤقت فقط؛ لم يعد مستخدماً في baseline النهائي.
- `desktop/dist-phase6/`: الحزمة التي بُنيت واختُبرت بعد إصلاح bootstrap.

ملف الجولة الكاملة يسجل `failed` في آخر سطر لأن أول نسخة من سيناريو الإبطال استخدمت heartbeat قبل إصلاح الخادم. البنود السابقة في الملف صحيحة وناجحة، وإعادة اختبار الإبطال بعد الإصلاح موثقة مستقلة في `session-admin-revoke-live.jsonl`.

## 7. الاختبارات النهائية

| المجموعة | النتيجة |
|---|---|
| Python full suite | `90 passed` |
| Desktop suite | `2 passed` |
| اختبارات websocket/audit المستهدفة قبل البناء | `7 passed` |
| JavaScript controller syntax | PASS |
| Packaged Desktop build | PASS |
| Audit chain | `true`، وعدد الأحداث 1260 عند الإغلاق |
| Docker services | جميع الخدمات المطلوبة تعمل، والـhealthchecks خضراء |

## 8. حالة baseline النهائية

- Access token: `480` دقيقة.
- Refresh token: السياسة الأصلية `30` يوماً.
- جلسات Desktop الأربع: access صالح `28800` ثانية وrefresh محفوظ.
- HR: active وactivated، و`token_version=2` بعد دورتي الإبطال المقصودتين.
- مزود النموذج: `http://host.docker.internal:60000/v1/chat/completions`.
- fault stub على 60010: متوقف.
- Context7 MCP: active وعلى URL الأصلي.
- Knowledge sources المؤقتة: صفر.
- تغييرات التصميم: صفر.
- Terminal/Code Execution: غير مسموحة ولم تُستخدم من Agent.

## 9. قرار البوابة

- إعادة activation بسبب انتهاء access الطبيعي: صفر.
- refresh races غير المستردة: صفر.
- تأثير الإبطال على مستخدم آخر: صفر.
- جلسة مبطلة بقيت قابلة للاستخدام بعد heartbeat: صفر بعد الإصلاح.
- `S0`: صفر.
- `S1` متبقٍ: صفر.

المرحلة السادسة **مغلقة بنجاح**، ويُسمح بالانتقال إلى **المرحلة السابعة: Soak Test وقياسات الموارد**.
