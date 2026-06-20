# رحلة العميل داخل المنصة

هذا الملف يشرح رحلة العميل من بداية تجهيز المنصة داخل Docker حتى التشغيل اليومي، مع توضيح أين يدخل المدير، أين يدخل الموظف، وما الذي يجب أن يحدث في كل مرحلة.

## 1. تجهيز وتشغيل المنصة

1. يشغل مالك النظام Docker stack الخاص بالاختبار أو الإنتاج.
2. يتم تشغيل الخدمات الأساسية:
   - API backend
   - Admin frontend
   - PostgreSQL
   - Redis
   - Hermes runtime
   - Hermes orchestrator
3. يتأكد مالك النظام أن الخدمات healthy.
4. يدخل مالك النظام إلى لوحة الإدارة من المتصفح.
5. يسجل الدخول بحساب المدير.

النتيجة المتوقعة:
- API يعمل.
- لوحة الإدارة تفتح.
- Hermes يظهر كـ running أو ready.
- لا توجد أخطاء في logs.

## 2. إعداد Hermes وملفات التشغيل

1. يدخل المدير إلى صفحة Hermes في لوحة الإدارة.
2. يتحقق من حالة Hermes.
3. إذا كان Hermes يحتاج مزامنة، يستخدم repair/sync من لوحة الإدارة.
4. يتأكد أن runtime جاهز لاستقبال profile وتشغيل agents.

النتيجة المتوقعة:
- Hermes status جاهز.
- يمكن إنشاء profile ومزامنته مع Hermes.

## 3. إنشاء Profile للموظفين

1. يدخل المدير إلى صفحة Profiles.
2. ينشئ profile جديد.
3. يحدد:
   - الاسم
   - slug
   - runtime type، وغالباً `hermes`
   - system prompt
   - agents.md
   - soul.md
   - skills
   - limits اليومية
   - providers المسموح بها
   - tools المسموح بها
4. يحفظ profile.
5. المنصة تزامن profile مع Hermes.

النتيجة المتوقعة:
- profile يظهر في القائمة.
- `hermes_sync_status = synced`.
- profile جاهز للاستخدام مع موظف.

## 4. إضافة مفاتيح LLM API

1. يدخل المدير إلى صفحة API Keys.
2. يضيف مفتاح LLM حسب طريقة الملكية:
   - platform key: مفتاح عام كاحتياط للنظام.
   - profile key: مفتاح مرتبط بـ profile محدد.
   - user key: مفتاح خاص بموظف معين.
3. يحدد provider مثل MiniMax أو OpenAI.
4. يحدد daily budget.
5. يحفظ المفتاح.

ترتيب اختيار المفتاح أثناء التشغيل:
1. user key
2. profile key
3. platform key

النتيجة المتوقعة:
- المفتاح محفوظ بشكل مشفر.
- النظام يستطيع تشغيل agent بدون إدخال المفتاح من الموظف.

## 5. إنشاء موظف

1. يدخل المدير إلى صفحة Employees.
2. ينشئ موظف جديد.
3. يحدد:
   - email
   - full name
   - department
   - role
   - max requests per day
   - max tokens per day
4. بعد الحفظ يحصل المدير على invite token.
5. يرسل المدير invite token للموظف.

النتيجة المتوقعة:
- الموظف موجود في النظام.
- حسابه غير مفعل بعد.
- يوجد invite token صالح للتفعيل.

## 6. ربط الموظف بـ Profile

1. يدخل المدير إلى صفحة Assignments.
2. يختار الموظف.
3. يختار profile.
4. يحدد priority.
5. يحفظ assignment.

النتيجة المتوقعة:
- الموظف أصبح مرتبطاً بالـ profile.
- عند المحادثة، النظام يستخدم profile المناسب لهذا الموظف.

## 7. تفعيل حساب الموظف

1. الموظف يستلم invite token.
2. يفتح واجهة التفعيل أو تطبيق سطح المكتب.
3. يدخل invite token.
4. يحدد كلمة مرور.
5. يرسل طلب التفعيل.

النتيجة المتوقعة:
- الحساب يصبح activated.
- يحصل الموظف على access token.
- يستطيع استخدام chat وTelegram والـ desktop.

## 8. استخدام الموظف للمحادثة

1. الموظف يرسل رسالة من الواجهة أو تطبيق desktop.
2. API يتحقق من:
   - أن الحساب مفعل.
   - أن الحساب active.
   - أن request quota لم ينته.
   - أن token quota لم ينته.
   - أن profile جاهز ومزامن.
   - أن provider مسموح لهذا profile.
   - أن API key متوفر.
3. النظام يرسل الطلب إلى Hermes.
4. Hermes runtime ينفذ agent.
5. النظام يحفظ:
   - user message
   - assistant message
   - agent run
   - run events
   - token usage
   - KPI

النتيجة المتوقعة:
- الموظف يحصل على رد.
- المحادثة تظهر في history.
- المدير يرى session/run/KPI في لوحة الإدارة.

## 9. المحادثات والبث

المنصة تدعم ثلاثة أنماط:

1. REST chat:
   - مناسب لطلب واحد ورد واحد.
2. SSE streaming:
   - مناسب للبث النصي عبر المتصفح.
3. WebSocket chat:
   - مناسب لتطبيق desktop والتجربة التفاعلية.

النتيجة المتوقعة:
- كل مسار ينشئ conversation ويحفظ الرسائل.
- لا تبقى DB connections مفتوحة بعد البث.

## 10. ربط Telegram

1. الموظف يطلب توليد bind code.
2. النظام ينشئ كود ربط مؤقت.
3. الموظف يرسل `/bind <code>` إلى Telegram bot.
4. Telegram webhook يصل إلى API.
5. النظام يربط telegram chat id بحساب الموظف.
6. بعد الربط يستطيع الموظف إرسال رسائل عبر Telegram.

النتيجة المتوقعة:
- Telegram chat id محفوظ للموظف.
- رسائل Telegram تمر عبر نفس profile وquota وHermes runtime.

## 11. مراقبة المدير

المدير يراجع:

1. Sessions:
   - المحادثات
   - الرسائل
   - agent runs
   - runtime type
2. KPIs:
   - messages sent
   - tokens used
   - total cost
3. Dashboard:
   - messages today
   - tokens today
   - profile usage
4. Activity feed:
   - تسجيل الدخول
   - WebSocket connect
   - message sent
5. Audit log:
   - العمليات الإدارية والحساسة

النتيجة المتوقعة:
- المدير يستطيع معرفة الاستخدام والتكاليف والمشاكل التشغيلية.

## 12. التشغيل اليومي في الإنتاج

1. المدير يضيف أو يحدث profiles حسب الفرق.
2. يضيف مفاتيح LLM حقيقية.
3. يربط Telegram bot الحقيقي.
4. ينشئ الموظفين ويرسل invite tokens.
5. يراقب KPIs وlogs.
6. يستخدم backup/restore scripts عند الحاجة.
7. يراقب quotas وbudgets.

## 13. ما تم اختباره داخل Docker

تم اختبار:

- login/logout/session security
- cookies وBearer auth
- employee activation
- Hermes status/repair/sync
- profile create/update/sync
- API key create/update
- employee create/update/quotas
- assignment create/list
- REST chat
- SSE chat
- WebSocket chat
- conversation history/title
- Telegram bind/webhook flow
- KPIs/dashboard/activity/audit
- admin session details
- API logs بعد الاختبار

## 14. ما يحتاج بيانات حقيقية عند الانتقال للإنتاج

هذه الأشياء جاهزة من ناحية الكود، لكنها تحتاج بيانات خارجية حقيقية:

- LLM API key حقيقي.
- Telegram bot token وbot username/id.
- domain وTLS على VPS.
- إعدادات backup storage في بيئة الإنتاج.
- مراقبة logs/metrics حسب السيرفر النهائي.
