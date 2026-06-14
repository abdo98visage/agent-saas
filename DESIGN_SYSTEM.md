# KarzounOS Design System

> نظام التصميم الرسمي لمنصة KarzounOS — مرجع موحد لكل الصفحات الحالية والمستقبلية.

---

## 🎨 الهوية البصرية

### الألوان

| الدور | اللون | HEX | الاستخدام |
|-------|-------|-----|-----------|
| **Primary** | Deep Indigo | `#6366F1` → `#4F46E5` | الأزرار الرئيسية، العناوين المتدرجة، الحالة النشطة في الـ sidebar |
| **Secondary** | Warm Amber | `#F59E0B` | التأكيدات، الـ secondary actions، gradient accents |
| **Success** | Emerald | `#10B981` → `#059669` | الحالات النشطة، الأونلاين، النجاح |
| **Error** | Red | `#EF4444` → `#DC2626` | الأخطاء، التعطيل، التحذيرات الحرجة |
| **Warning** | Amber | `#F59E0B` → `#D97706` | التنبيهات، الـ pending states |
| **Info** | Blue | `#3B82F6` → `#2563EB` | المعلومات، الـ links، الأيقونات الثانوية |
| **Purple** | Violet | `#8B5CF6` → `#7C3AED` | البروفايلات، الـ tokens، الـ AI-related |
| **Neutral 50** | Background | `#F8FAFC` | خلفيات عامة |
| **Neutral 100** | Card BG | `#F1F5F9` | خلفيات البطاقات الثانوية |
| **Neutral 200** | Borders | `#E2E8F0` | الحدود |
| **Neutral 400** | Muted Text | `#94A3B8` | نصوص ثانوية |
| **Neutral 600** | Body Text | `#475569` | النصوص العادية |
| **Neutral 800** | Headings | `#1E293B` | العناوين |
| **Neutral 900** | Title | `#0F172A` | العناوين الرئيسية |

### الخطوط

| الخط | الاستخدام | الأوزان |
|------|-----------|---------|
| **Cairo** | العربية — أساسي | 400, 500, 600, 700 |
| **Inter** | الإنجليزية — ثانوي | 400, 500, 600, 700 |
| **JetBrains Mono** | الكود، الـ IDs | 400, 500 |

**قاعدة:** كل النصوص العربية بـ Cairo، الكود والأرقام الإنجليزية بـ JetBrains Mono.

---

## 🧱 المكونات (Components)

### 1. البطاقات — `kos-card`

```css
.kos-card {
  border-radius: 14px;
  border: 1px solid var(--border);
  background: white;
  box-shadow: var(--shadow-md);
  overflow: hidden;
  transition: all 0.2s ease;
}
.kos-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
.kos-card .card-gradient-top {
  height: 3px;
  background: linear-gradient(90deg, #6366F1, #F59E0B);
}
```

**قاعدة الاستخدام:**
- كل `<Card>` في الصفحات يأخذ `className="kos-card"`
- كل بطاقة فيها `<div className="card-gradient-top" />` في الأعلى
- لتخصيص لون الشريط العلوي: `style={{ background: "linear-gradient(90deg, #color1, #color2)" }}`
- الألوان المفضلة للشريط: indigo (افتراضي), emerald (نجاح), amber (تحذير), blue (معلومات), purple (AI)

### 2. الأزرار — `kos-gradient-btn`

```css
.kos-gradient-btn {
  background: linear-gradient(135deg, #6366F1, #4F46E5);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  transition: all 0.2s ease;
}
.kos-gradient-btn:hover {
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}
```

**قاعدة الاستخدام:**
- أزرار الإجراء الرئيسي (إضافة، حفظ، تطبيق) → `kos-gradient-btn text-white`
- أزرار ثانوية → `variant="outline"`
- أزرار تحذير → `variant="ghost"` مع أيقونة حمراء

### 3. حقول الإدخال — `kos-input`

```css
.kos-input {
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
  font-family: 'Cairo', sans-serif;
  font-size: 14px;
  transition: all 0.2s ease;
  background: white;
}
.kos-input:focus {
  border-color: #6366F1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}
```

**قاعدة:** كل `<Input>` و `<select>` و `<textarea>` يأخذ `className="kos-input"`

### 4. الشارات — Badges

```css
.kos-badge-green  { background: #ECFDF5; color: #059669; }
.kos-badge-red    { background: #FEF2F2; color: #DC2626; }
.kos-badge-amber  { background: #FFFBEB; color: #D97706; }
.kos-badge-blue   { background: #EEF2FF; color: #4F46E5; }
.kos-badge-purple { background: #F5F3FF; color: #7C3AED; }
.kos-badge-gray   { background: #F1F5F9; color: #64748B; }
```

**قاعدة:**
- الحالة النشطة/مفعّل → `kos-badge-green`
- معطل/محذوف → `kos-badge-red`
- تحذير/انتظار → `kos-badge-amber`
- معلومات/صلاحية → `kos-badge-blue`
- بروفايل/AI → `kos-badge-purple`
- محايد/بدون قيمة → `kos-badge-gray`

### 5. العنوان الرئيسي — `kos-gradient-text`

```css
.kos-gradient-text {
  background: linear-gradient(135deg, #6366F1, #4F46E5);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

**قاعدة:** كل `h1` في الصفحة يأخذ `kos-gradient-text`

### 6. حركة الدخول — `kos-animate-in`

```css
@keyframes kos-fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.kos-animate-in {
  animation: kos-fade-in 0.4s ease forwards;
}
```

**قاعدة:** الـ container الرئيسي في كل صفحة يأخذ `kos-animate-in`

### 7. مؤشر الأونلاين — `kos-online-pulse`

```css
.kos-online-pulse {
  background: #10B981;
  border-radius: 50%;
  animation: kos-pulse 2s ease-in-out infinite;
}
```

**قاعدة:** يُستخدم فقط لحالة المتصل الآن

---

## 📐 هيكلية الصفحة (Page Layout)

كل صفحة جديدة يجب أن تتبع هذا الهيكل:

```tsx
export default function MyPage() {
  return (
    <div className="p-8 space-y-6 kos-animate-in" dir="rtl">
      {/* 1. Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight kos-gradient-text">اسم الصفحة</h1>
          <p className="text-muted-foreground mt-1">وصف مختصر بالعربية</p>
        </div>
        {/* زر الإجراء الرئيسي (اختياري) */}
        <Button className="kos-gradient-btn text-white">
          <Icon className="ml-2 h-4 w-4" />
          إجراء
        </Button>
      </div>

      {/* 2. Summary Cards (اختياري — 3-4 بطاقات) */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="kos-card">
          <div className="card-gradient-top" />
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">الوصف</p>
                <p className="text-2xl font-bold">القيمة</p>
              </div>
              <Icon className="h-8 w-8 text-indigo-600" />
            </div>
          </CardContent>
        </Card>
        {/* ... باقي البطاقات */}
      </div>

      {/* 3. Content (Table / Cards / Charts) */}
      <Card className="kos-card">
        <CardContent className="pt-6">
          {/* المحتوى */}
        </CardContent>
      </Card>

      {/* 4. Dialogs (اختياري) */}
    </div>
  );
}
```

---

## 📋 قواعد ثابتة (Must Follow)

1. **RTL إلزامي** — `dir="rtl"` في الـ container الرئيسي لكل صفحة
2. **العربية إلزامية** — كل labels, buttons, headings, descriptions بالعربية
3. **kos-card إلزامي** — كل `<Card>` يأخذ `kos-card`
4. **Gradient top إلزامي** — كل kos-card فيها `card-gradient-top`
5. **kos-gradient-text إلزامي** — كل h1 principal
6. **kos-input إلزامي** — كل inputs/selects/textareas
7. **kos-gradient-btn إلزامي** — أزرار الإجراء الرئيسي
8. **kos-animate-in إلزامي** — container الرئيسي
9. **Badges ملونة** — استخدام `kos-badge-*` المناسب للحالة
10. **Summary Cards** — كل صفحة فيها بطاقات إحصائية مناسبة

---

## 🎯 أمثلة سريعة

### بطاقة إحصائية جديدة

```tsx
<Card className="kos-card">
  <div className="card-gradient-top" style={{ background: "linear-gradient(90deg, #8B5CF6, #7C3AED)" }} />
  <CardContent className="pt-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-muted-foreground">الوصف</p>
        <p className="text-2xl font-bold text-purple-600">123</p>
      </div>
      <Icon className="h-8 w-8 text-purple-600" />
    </div>
  </CardContent>
</Card>
```

### Badge حالة

```tsx
<Badge className={isActive ? "kos-badge-green" : "kos-badge-red"}>
  {isActive ? "نشط" : "معطل"}
</Badge>
```

### زر إجراء

```tsx
<Button className="kos-gradient-btn text-white" onClick={handleAction}>
  <Plus className="ml-2 h-4 w-4" />
  إضافة جديد
</Button>
```
