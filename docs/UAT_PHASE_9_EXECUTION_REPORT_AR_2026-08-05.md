# تقرير تنفيذ المرحلة التاسعة — Upgrade وBackup/Restore

التاريخ: 2026-08-05  
الحالة: **PASS وظيفي — بوابة التوقيع والتشفير التشغيلية ما زالت مطلوبة**

## 1. الخلاصة

نجح upgrade وrollback الحيان أمام أربعة تطبيقات Desktop، ونجحت الاستعادة إلى Backend معزول وفارغ مع قاعدة وvolumes مستقلة، ثم استطاع الموظفون الأربعة تسجيل الدخول ومتابعة محادثاتهم القديمة من النسخة المستعادة. لم تُنفذ بعد تجربة الحزمة الموقعة والنسخة المشفرة بأداة الإنتاج لأن المضيف لا يحتوي `cosign` أو `gpg` ولا توجد مفاتيح الشركة؛ لذلك لا تزال هذه بوابة تشغيلية قبل Production Go وليست عيباً في مسار المستخدم المختبر.

## 2. Upgrade أمام أربعة Desktop

كانت تطبيقات Desktop packaged الأربعة مفتوحة على منافذ CDP من 9351 إلى 9354. أرسل كل مستخدم رسالة قبل الترقية، ثم أعيد إنشاء API من الصورة الجديدة، وبعد العودة أُرسلت متابعة في المحادثة نفسها.

النتائج:

- المستخدمون قبل upgrade: 4/4 ناجحون.
- API ready بعد upgrade: 2.830 ثانية.
- WebSocket reconnect لكل Desktop: خلال 4.120 ثانية.
- Conversation id بقي نفسه لكل مستخدم.
- رسالة ما بعد upgrade حُفظت مرة واحدة لكل مستخدم.
- لا إعادة activation أو login يدوية.

## 3. فشل Postflight وRollback

تم إيقاف API كما يحدث عند cutover، ثم شُغلت candidate تجريبية تنتهي بالرمز 42. اعتُبر postflight فاشلاً، وأعيدت الصورة السابقة immutable.

- اكتشاف candidate الفاشلة: ناجح، exit code=42.
- API ready بعد rollback: 1.849 ثانية.
- Desktop reconnect بعد rollback: 2.367 ثانية.
- المستخدمون بعد rollback: 4/4 ناجحون.
- نفس المحادثات بقيت مفتوحة.
- رسائل ما بعد rollback حُفظت مرة واحدة.
- لا فقد بيانات أو stuck runs.

الدليل: `uat-evidence/phase9-upgrade-four-desktops.jsonl`.

## 4. Restore drill الرسمي

نُفذ `deploy/restore_drill.ps1` أولاً على dump حديث داخل قاعدة مؤقتة:

- schema: `repair_audit_chain_order`.
- source/restored: 86 users، 87 profiles، 6,382 messages، 1,386 audit events، 33 knowledge sources، 33 documents، 32 chunks.
- Audit chain: سليمة.
- RTO: 6 ثوانٍ مقابل هدف 300 ثانية.

## 5. الاستعادة الكاملة إلى Backend معزول

أُنشئت بيئة مؤقتة مستقلة تحتوي:

- PostgreSQL database مستعادة باسم منفصل.
- volumes جديدة لـHermes profiles وattachments وKnowledge.
- Hermes Runtime مستقل.
- Hermes Orchestrator مستقل.
- FastAPI مستقل على المنفذ 8012.

لم تتصل الاختبارات بقاعدة الإنتاج الأصلية بعد بدء الاستعادة، ولم توقف الخدمات الأصلية. بعد الاختبار حُذفت الحاويات والvolumes وقاعدة الاستعادة المؤقتة المسماة صراحة.

### تطابق البيانات النهائي

| العنصر | المصدر | المستعاد |
|---|---:|---:|
| Users | 86 | 86 |
| Profiles | 87 | 87 |
| Sessions | 1,083 | 1,083 |
| Messages | 6,430 | 6,430 |
| Agent runs | 3,255 | 3,255 |
| Audit events | 1,388 | 1,388 |
| Knowledge sources | 33 | 33 |
| Knowledge documents | 33 | 33 |
| Knowledge chunks | 32 | 32 |
| MCP servers | 1 | 1 |
| Profile MCP bindings | 8 | 8 |

### تطابق الملفات

| Volume | المصدر | المستعاد |
|---|---:|---:|
| Hermes profiles | 468 files | 468 files |
| Attachments | 1 file | 1 file |
| Knowledge | 1 file | 1 file |

تم إنشاء attachment PNG حقيقي قبل snapshot، وحُفظ في الرسالة مع SHA-256 وobject key، ثم ظهر العدد نفسه في volume المستعادة. وبذلك لا يعتمد اختبار attachments على حالة 0→0.

### RPO/RTO ومتابعة المحادثة

- RPO في snapshot المختبرة: صفر بالنسبة إلى لحظة `pg_dump` ونسخ volumes؛ جميع الأعداد تطابقت.
- RTO المقاس حتى `API ready`: 11 ثانية مقابل هدف 300 ثانية.
- Audit chain في النسخة المستعادة: سليمة قبل وبعد استخدام الموظفين.
- الموظفون الأربعة سجلوا الدخول في الـBackend المستعاد.
- كل موظف فتح Conversation قديمة وسأل عن CAP marker من الدور السابق.
- النتيجة: 4/4 أعادوا marker الصحيح، من دون اختلاط بين المحادثات.

الدليل: `uat-evidence/phase9-restore-four-users.json`.

## 6. اختبارات regression والحالة النهائية

- Python: 92/92 ناجحة.
- Desktop: 2/2 ناجحة.
- جميع خدمات البيئة الأصلية running/healthy، restarts=0.
- Audit chain الأصلية: سليمة.
- running/pending agent runs: صفر.
- pending approvals: صفر.
- ungranted DB locks: صفر.
- Runtime temp dirs: صفر.
- لا موارد Phase 9 مؤقتة باقية بعد cleanup.

## 7. البوابة التشغيلية غير المنفذة

مسار Linux الإنتاجي يفرض:

- تشفير backup بواسطة مفتاح GPG عام محفوظ خارج المضيف.
- تحقق release manifest وsignature بواسطة `cosign`.
- حزمة إصدار موقعة ومفاتيح registry/release.

المضيف الحالي لا يحتوي `gpg` أو `cosign`، ولم يزوّد بمفتاح GPG عام أو مفتاح Cosign عام أو release bundle موقعة. لا يجوز توليد مفاتيح إنتاج وهمية واعتبارها قبولاً للشركة. المطلوب لإغلاق البوابة:

1. تثبيت `gpg` و`cosign` على staging Linux المطابق للعميل.
2. تزويد public GPG recipient من مفتاح خاص محفوظ خارج الخادم.
3. تزويد Cosign public key وحزمة release موقعة.
4. تشغيل `backup.sh` ثم `upgrade.sh` ثم `restore.sh` وتسجيل الأدلة نفسها.

## 8. القرار

منظور المستخدم واستعادة البيانات والملفات وupgrade/rollback ناجحة. تبقى المرحلة **مشروطة** فقط بالتجربة cryptographic/operational أعلاه على Staging Linux. لا يوجد تعديل تصميمي أو تغيير للوظائف الأساسية في هذه المرحلة.
