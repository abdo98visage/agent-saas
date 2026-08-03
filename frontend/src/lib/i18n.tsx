"use client";

import { createContext, useContext, useEffect, useState } from "react";

type Language = "ar" | "en";

interface I18nContextValue {
  language: Language;
  dir: "rtl" | "ltr";
  setLanguage: (language: Language) => void;
  t: (text: string) => string;
  safeText: (text: string) => string;
}

const STORAGE_KEY = "admin-language";
let reverseTranslations: Record<string, string> = {};

function translateValue(language: Language, value: string) {
  if (language === "ar") {
    return translations[value] || value;
  }

  return reverseTranslations[value] || value;
}

function sanitizeProductNames(language: Language, value: string) {
  return value.replace(/hermes|هرمز|هيرمس/gi, language === "ar" ? "الوكلاء الأذكياء" : "Smart Agents");
}

const translations: Record<string, string> = {
  "Admin dashboard": "لوحة التحكم",
  "Workspace connected": "مساحة العمل متصلة",
  "Sign Out": "تسجيل الخروج",
  "Arabic": "العربية",
  "English": "English",
  "Dashboard": "لوحة التحكم",
  "Employees": "الموظفون",
  "Profiles": "البروفايلات",
  "Skills": "المهارات",
  "Assignments": "التعيينات",
  "Sessions": "الجلسات",
  "KPIs": "مؤشرات الأداء",
  "API Keys": "مفاتيح API",
  "Agent Tester": "مختبر الوكيل",
  "Agent Runtime": "تشغيل الوكلاء",
  "Audit Log": "سجل التدقيق",
  "Templates": "القوالب",
  "MCP": "MCP",
  "Manage approved MCP servers, tools, and profile access.": "إدارة خوادم MCP المعتمدة وأدواتها وصلاحيات البروفايلات.",
  "Add MCP Server": "إضافة خادم MCP",
  "Edit MCP Server": "تعديل خادم MCP",
  "Approved MCP Servers": "خوادم MCP المعتمدة",
  "Discovered Tools": "الأدوات المكتشفة",
  "Profile MCP Access": "صلاحيات MCP للبروفايلات",
  "Profile bindings": "ارتباطات البروفايلات",
  "HTTPS MCP URL": "رابط MCP الآمن HTTPS",
  "Authentication": "المصادقة",
  "No authentication": "بدون مصادقة",
  "Credential ownership": "ملكية بيانات الاتصال",
  "Managed by administrator": "تدار من المدير",
  "Provided by each employee": "يقدمها كل موظف",
  "API key header": "ترويسة مفتاح API",
  "Platform credential": "بيانات اتصال المنصة",
  "Temporary discovery credential": "بيانات مؤقتة لاكتشاف الأدوات",
  "Leave blank to keep the current credential": "اتركه فارغاً للاحتفاظ بالقيمة الحالية",
  "Discover": "اكتشاف",
  "Allow": "سماح",
  "Require approval": "يتطلب موافقة",
  "Discover tools before assigning this server.": "اكتشف الأدوات قبل إتاحة الخادم للبروفايل.",
  "No MCP servers configured.": "لا توجد خوادم MCP مضافة.",
  "Select at least one allowed tool": "اختر أداة مسموحة واحدة على الأقل",
  "Enter a temporary credential for discovery": "أدخل بيانات اتصال مؤقتة لاكتشاف الأدوات",
  "Delete this MCP server and all profile bindings?": "حذف خادم MCP وجميع ارتباطاته بالبروفايلات؟",
  "MCP server created": "تم إنشاء خادم MCP",
  "MCP server updated": "تم تحديث خادم MCP",
  "MCP server deleted": "تم حذف خادم MCP",
  "MCP tools discovered": "تم اكتشاف أدوات MCP",
  "MCP discovery failed": "فشل اكتشاف أدوات MCP",
  "Profile MCP access saved": "تم حفظ صلاحيات MCP للبروفايل",
  "Profile MCP access removed": "تمت إزالة صلاحيات MCP من البروفايل",
  "Signed in": "تم تسجيل الدخول",
  "Failed to sign in": "فشل تسجيل الدخول",
  "Admin access": "وصول المدير",
  "Sign In": "تسجيل الدخول",
  "Use your admin credentials to open the dashboard.": "استخدم بيانات المدير لفتح لوحة التحكم.",
  "Email": "البريد الإلكتروني",
  "Password": "كلمة المرور",
  "Signing in...": "جارٍ تسجيل الدخول...",
  "Loading...": "جارٍ التحميل...",
  "Connected": "متصل",
  "Disconnected": "غير متصل",
  "Sent message": "أرسل رسالة",
  "Logged in": "سجّل الدخول",
  "Activated account": "فعّل الحساب",
  "Operational status for employees, sessions, and usage.": "الحالة التشغيلية للموظفين والجلسات والاستخدام.",
  "online": "متصل",
  "active": "نشط",
  "Online Now": "المتصلون الآن",
  "Messages Today": "رسائل اليوم",
  "Tokens Today": "توكنز اليوم",
  "Desktop app currently connected": "تطبيق الديسكتوب متصل حالياً",
  "Messages, last 7 days": "الرسائل خلال آخر 7 أيام",
  "Tokens, last 7 days": "التوكنز خلال آخر 7 أيام",
  "Activity counts": "إحصاءات النشاط",
  "Top users today": "أكثر المستخدمين نشاطاً اليوم",
  "messages": "رسائل",
  "tokens": "توكنز",
  "No activity yet.": "لا يوجد نشاط بعد.",
  "Online users": "المستخدمون المتصلون",
  "Nobody online right now.": "لا يوجد أحد متصل الآن.",
  "Active Alerts": "التنبيهات النشطة",
  "No active alerts.": "لا توجد تنبيهات نشطة.",
  "Recent activity": "آخر النشاطات",
  "No recent activity.": "لا يوجد نشاط حديث.",
  "Manage employee accounts, roles, and daily usage limits.": "إدارة حسابات الموظفين والأدوار وحدود الاستخدام اليومية.",
  "Add Employee": "إضافة موظف",
  "Create Employee": "إنشاء موظف",
  "Full Name": "الاسم الكامل",
  "Department": "القسم",
  "Daily Token Limit": "حد التوكنز اليومي",
  "Daily Request Limit": "حد الطلبات اليومي",
  "Total Employees": "إجمالي الموظفين",
  "Active": "نشط",
  "Disable": "تعطيل",
  "Disabled": "معطل",
  "Name": "الاسم",
  "Role": "الدور",
  "Status": "الحالة",
  "Limits": "الحدود",
  "Actions": "الإجراءات",
  "employee": "موظف",
  "admin": "مدير",
  "tok": "توكن",
  "req": "طلب",
  "No employees found.": "لم يتم العثور على موظفين.",
  "Edit Employee": "تعديل الموظف",
  "Save Changes": "حفظ التغييرات",
  "Disable this employee?": "هل تريد تعطيل هذا الموظف؟",
  "Employee created": "تم إنشاء الموظف",
  "Activation link copied": "تم نسخ رابط التفعيل",
  "Desktop invite copied": "تم نسخ دعوة تطبيق سطح المكتب",
  "Desktop sharing package": "حزمة مشاركة تطبيق سطح المكتب",
  "Employee desktop activation": "تفعيل تطبيق الدسكتوب للموظف",
  "Copy desktop activation link": "نسخ رابط تفعيل الدسكتوب",
  "Create and copy desktop activation link": "إنشاء ونسخ رابط تفعيل الدسكتوب",
  "Reissue and copy desktop activation link": "إعادة إصدار ونسخ رابط تفعيل الدسكتوب",
  "Reissuing the activation link signs the employee out of existing desktop sessions.": "إعادة إصدار الرابط تسجّل خروج الموظف من جلسات الدسكتوب الحالية.",
  "Failed to create desktop invite": "فشل إنشاء دعوة تفعيل الدسكتوب",
  "This employee has already activated the desktop app.": "هذا الموظف فعّل تطبيق الدسكتوب مسبقاً.",
  "Desktop app downloads": "تحميل تطبيق الدسكتوب",
  "The installer is shared by all employees. Activation is employee-specific.": "ملف التثبيت مشترك لكل الموظفين. التفعيل خاص بكل موظف.",
  "Download Windows app": "تحميل تطبيق Windows",
  "Download macOS app": "تحميل تطبيق macOS",
  "Copy full desktop invite": "نسخ دعوة الدسكتوب كاملة",
  "Failed to create employee": "فشل إنشاء الموظف",
  "Employee updated": "تم تحديث الموظف",
  "Failed to update employee": "فشل تحديث الموظف",
  "Employee disabled": "تم تعطيل الموظف",
  "Failed to disable employee": "فشل تعطيل الموظف",
  "Smart Agent Profiles": "بروفايلات الوكلاء الأذكياء",
  "Manage AGENTS.md, soul, skills, and system prompts per role.": "إدارة AGENTS.md وملف soul والمهارات وتعليمات النظام لكل دور.",
  "Add Profile": "إضافة بروفايل",
  "Create Profile": "إنشاء بروفايل",
  "Slug": "المعرّف",
  "SOUL.md": "ملف SOUL.md",
  "Hold Ctrl or Cmd to select multiple skills.": "اضغط Ctrl أو Cmd لاختيار عدة مهارات.",
  "System Prompt": "تعليمات النظام",
  "Daily Tokens": "التوكنز اليومية",
  "Daily Requests": "الطلبات اليومية",
  "Cost Budget": "ميزانية التكلفة",
  "Allowed Providers": "المزوّدون المسموحون",
  "MCP Servers": "خوادم MCP",
  "Allowed Tools": "الأدوات المسموحة",
  "Approval Tools": "أدوات تحتاج موافقة",
  "Inactive": "غير نشط",
  "pending": "قيد الانتظار",
  "synced": "متزامن",
  "low": "منخفض",
  "medium": "متوسط",
  "high": "مرتفع",
  "critical": "حرج",
  "Skills:": "المهارات:",
  "View": "عرض",
  "Edit": "تعديل",
  "Sync": "مزامنة",
  "No profiles created yet.": "لا توجد ملفات حتى الآن.",
  "No AGENTS.md content.": "لا يوجد محتوى AGENTS.md.",
  "Delete this profile?": "هل تريد حذف هذا الملف؟",
  "Profile created": "تم إنشاء الملف",
  "Failed to create profile": "فشل إنشاء الملف",
  "Profile updated": "تم تحديث الملف",
  "Failed to update profile": "فشل تحديث الملف",
  "Profile deleted": "تم حذف الملف",
  "Failed to delete profile": "فشل حذف الملف",
  "Profile sync requested": "تم طلب مزامنة الملف",
  "Failed to sync profile": "فشل مزامنة الملف",
  "Edit Profile": "تعديل الملف",
  "Create reusable agent skills and attach them to profiles.": "أنشئ مهارات للوكلاء قابلة لإعادة الاستخدام واربطها بالبروفايلات.",
  "Add Skill": "إضافة مهارة",
  "Create Skill": "إنشاء مهارة",
  "Description": "الوصف",
  "Instructions (SKILL.md body)": "التعليمات (محتوى SKILL.md)",
  "Total Skills": "إجمالي المهارات",
  "No description": "لا يوجد وصف",
  "No instructions yet.": "لا توجد تعليمات بعد.",
  "Delete": "حذف",
  "No skills defined yet.": "لا توجد مهارات معرفة بعد.",
  "Delete this skill?": "هل تريد حذف هذه المهارة؟",
  "Skill created": "تم إنشاء المهارة",
  "Failed to create skill": "فشل إنشاء المهارة",
  "Skill updated": "تم تحديث المهارة",
  "Failed to update skill": "فشل تحديث المهارة",
  "Skill deleted": "تم حذف المهارة",
  "Failed to delete skill": "فشل حذف المهارة",
  "Edit Skill": "تعديل المهارة",
  "Profile Assignments": "تعيينات البروفايلات",
  "Assign employees to smart agent profiles and control priority order.": "اربط الموظفين ببروفايلات الوكلاء الأذكياء وتحكم بترتيب الأولوية.",
  "Create Assignment": "إنشاء تعيين",
  "Assign Profile": "تعيين بروفايل",
  "Employee": "الموظف",
  "Select employee...": "اختر موظفاً...",
  "Profile": "البروفايل",
  "Select profile...": "اختر بروفايل...",
  "Priority": "الأولوية",
  "Save Assignment": "حفظ التعيين",
  "Assignment removed": "تمت إزالة التعيين",
  "Failed to remove assignment": "فشلت إزالة التعيين",
  "Assignment created": "تم إنشاء التعيين",
  "Failed to create assignment": "فشل إنشاء التعيين",
  "Delete this assignment?": "هل تريد حذف هذا التعيين؟",
  "key ready": "المفتاح جاهز",
  "no profile key": "لا يوجد مفتاح للملف",
  "No assignments yet.": "لا توجد تعيينات بعد.",
  "Inspect conversation history by user, profile, and date.": "استعرض سجل المحادثات حسب المستخدم والبروفايل والتاريخ.",
  "User": "المستخدم",
  "From Date": "من تاريخ",
  "Apply Filters": "تطبيق الفلاتر",
  "Total Sessions": "إجمالي الجلسات",
  "Today": "اليوم",
  "Title": "العنوان",
  "Created": "تاريخ الإنشاء",
  "Untitled": "بدون عنوان",
  "default": "افتراضي",
  "No sessions found.": "لم يتم العثور على جلسات.",
  "Session Detail": "تفاصيل الجلسة",
  "Usage Analytics": "تحليلات الاستخدام",
  "Track monthly token and cost consumption by employee and by agent.": "متابعة استهلاك التوكنز والتكلفة شهرياً حسب الموظف والوكيل.",
  "Month": "الشهر",
  "All employees": "كل الموظفين",
  "Agent / Profile": "الوكيل / الملف",
  "All agents": "كل الوكلاء",
  "avg tokens/run": "متوسط توكنز/تشغيل",
  "KPI tokens tracked": "توكنز KPI متتبعة",
  "Monthly Cost": "التكلفة الشهرية",
  "Total Tokens": "إجمالي التوكنز",
  "Runs": "التشغيلات",
  "Active Pricing": "التسعير النشط",
  "Not set": "غير مضبوط",
  "Employee Consumption This Month": "استهلاك الموظفين هذا الشهر",
  "Input Tokens": "توكنز الإدخال",
  "Output Tokens": "توكنز الإخراج",
  "Cost": "التكلفة",
  "Agent Consumption This Month": "استهلاك الوكلاء هذا الشهر",
  "Agent": "الوكيل",
  "unassigned": "غير معيّن",
  "Employee x Agent Matrix": "مصفوفة الموظف × الوكيل",
  "Input": "إدخال",
  "Output": "إخراج",
  "No monthly usage rows yet.": "لا توجد سجلات استخدام شهرية بعد.",
  "Manage profile, employee override, and platform provider credentials.": "إدارة مفاتيح الملفات ومفاتيح التجاوز للموظفين وبيانات مزوّد المنصة.",
  "Add Key": "إضافة مفتاح",
  "Create API Key": "إنشاء مفتاح API",
  "Owner Type": "نوع المالك",
  "Profile key": "مفتاح ملف",
  "Employee override key": "مفتاح تجاوز للموظف",
  "Platform fallback key": "مفتاح احتياطي للمنصة",
  "Select employee": "اختر موظفاً",
  "Select profile": "اختر بروفايل",
  "Provider": "المزوّد",
  "API Key": "مفتاح API",
  "Daily Budget": "الميزانية اليومية",
  "Create Key": "إنشاء المفتاح",
  "Keys": "المفاتيح",
  "Total Budget": "إجمالي الميزانية",
  "Spent Today": "المستهلك اليوم",
  "MiniMax Monthly Pricing Model": "نموذج تسعير MiniMax الشهري",
  "Monthly Price (USD)": "السعر الشهري (USD)",
  "Monthly Token Allowance": "حصة التوكنز الشهرية",
  "Currency": "العملة",
  "Save Pricing": "حفظ التسعير",
  "Current rate:": "السعر الحالي:",
  "No active pricing configured yet.": "لا يوجد تسعير نشط مضبوط حتى الآن.",
  "Owner:": "المالك:",
  "Daily budget:": "الميزانية اليومية:",
  "Spent today:": "المستهلك اليوم:",
  "platform": "المنصة",
  "No API keys configured yet.": "لا توجد مفاتيح API مضبوطة بعد.",
  "Edit API Key": "تعديل مفتاح API",
  "Delete this API key?": "هل تريد حذف مفتاح API هذا؟",
  "API key created": "تم إنشاء مفتاح API",
  "Failed to create API key": "فشل إنشاء مفتاح API",
  "API key updated": "تم تحديث مفتاح API",
  "Failed to update API key": "فشل تحديث مفتاح API",
  "API key deleted": "تم حذف مفتاح API",
  "Failed to delete API key": "فشل حذف مفتاح API",
  "MiniMax pricing updated": "تم تحديث تسعير MiniMax",
  "Failed to update pricing": "فشل تحديث التسعير",
  "New Test Chat": "محادثة اختبار جديدة",
  "Test Controls": "أدوات الاختبار",
  "Optional Project Context": "سياق مشروع اختياري",
  "Optional context sent with this test message.": "سياق اختياري يتم إرساله مع رسالة الاختبار.",
  "Message": "الرسالة",
  "Write the admin test message here.": "اكتب رسالة الاختبار هنا.",
  "Testing agent...": "جارٍ اختبار الوكيل...",
  "Send Test Message": "إرسال رسالة اختبار",
  "Current conversation": "المحادثة الحالية",
  "No active conversation yet.": "لا توجد محادثة نشطة بعد.",
  "Test any agent from inside the platform and verify the real response and execution details.": "اختبر أي agent من داخل المنصة نفسها وتحقق من الرد الفعلي وبيانات التنفيذ.",
  "providers:": "المزوّدون:",
  "Choose an agent, then send a test message. Each reply will show the real content along with the model, URL, tokens, and cost.": "اختر agent ثم أرسل رسالة اختبار. كل رد سيعرض المحتوى الحقيقي مع الـ model والـ URL والتوكنز والتكلفة.",
  "Admin message": "رسالة المدير",
  "Agent response": "رد الوكيل",
  "Model": "النموذج",
  "Provider / Runtime": "المزوّد / بيئة التشغيل",
  "Latency": "زمن الاستجابة",
  "Request URL": "رابط الطلب",
  "Profile Used": "الملف المستخدم",
  "n/a": "غير متوفر",
  "Failed to load profiles": "فشل تحميل الملفات",
  "Agent test failed": "فشل اختبار الوكيل",
  "Install, health-check, restart, and repair the agent execution layer.": "ثبّت طبقة تشغيل الوكلاء وافحصها وأعد تشغيلها أو إصلاحها.",
  "Check Health": "فحص الحالة",
  "Runtime": "بيئة التشغيل",
  "Installed": "مثبّت",
  "Not installed": "غير مثبّت",
  "Version": "الإصدار",
  "Unknown": "غير معروف",
  "Failed Syncs": "المزامنات الفاشلة",
  "Lifecycle Controls": "أزرار التحكم",
  "Install": "تثبيت",
  "Start": "تشغيل",
  "Restart": "إعادة تشغيل",
  "Stop": "إيقاف",
  "Repair Sync": "إصلاح المزامنة",
  "Runtime Details": "تفاصيل التشغيل",
  "Docker image:": "صورة Docker:",
  "Not reported": "غير متوفر",
  "Queue health:": "حالة الطابور:",
  "Run health:": "حالة التشغيل:",
  "Last sync:": "آخر مزامنة:",
  "No logs available.": "لا توجد سجلات متاحة.",
  "Failed to load agent runtime status": "فشل تحميل حالة تشغيل الوكلاء",
  "Smart Agents": "الوكلاء الأذكياء",
  "Direct Model": "النموذج المباشر",
  "Agent action requested": "تم طلب إجراء تشغيل الوكلاء",
  "Agent action failed": "فشل إجراء تشغيل الوكلاء",
  "Agent profile synchronization failed.": "فشلت مزامنة بروفايل الوكيل.",
  "requested": "تم الطلب",
  "failed": "فشل",
  "running": "يعمل",
  "unknown": "غير معروف",
  "available": "متاح",
  "healthy": "سليم",
  "degraded": "متراجع",
  "stopped": "متوقف",
  "Track privileged actions and changes across the platform.": "متابعة الإجراءات الحساسة والتغييرات عبر المنصة.",
  "Total": "الإجمالي",
  "Adds": "الإضافات",
  "Updates": "التحديثات",
  "Disables": "التعطيلات",
  "IP": "IP",
  "Details": "التفاصيل",
  "No audit events yet.": "لا توجد أحداث تدقيق بعد.",
  "Agent Templates": "قوالب الوكلاء",
  "Reusable model and tool presets for future agents.": "إعدادات جاهزة للنماذج والأدوات للوكلاء المستقبليين.",
  "General": "عام",
  "Tools:": "الأدوات:",
  "Temperature:": "درجة الحرارة:",
  "tool": "أداة",
  "No templates configured yet.": "لا توجد قوالب مضبوطة بعد.",
};

reverseTranslations = Object.fromEntries(
  Object.entries(translations).map(([english, arabic]) => [arabic, english]),
);

const I18nContext = createContext<I18nContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setCurrentLanguage] = useState<Language>("ar");
  const [hasLoadedStoredLanguage, setHasLoadedStoredLanguage] = useState(false);

  useEffect(() => {
    let stored: string | null = null;

    try {
      stored = window.localStorage?.getItem(STORAGE_KEY) || null;
    } catch {
      stored = null;
    }

    const timer = window.setTimeout(() => {
      setCurrentLanguage(stored === "en" ? "en" : "ar");
      setHasLoadedStoredLanguage(true);
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    if (!hasLoadedStoredLanguage) {
      return;
    }

    document.documentElement.lang = language;
    document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
    const nativeConfirm = window.confirm.bind(window);
    window.confirm = (message?: string) => nativeConfirm(translateValue(language, String(message ?? "")));

    return () => {
      window.confirm = nativeConfirm;
    };
  }, [hasLoadedStoredLanguage, language]);

  const setLanguage = (nextLanguage: Language) => {
    document.documentElement.lang = nextLanguage;
    document.documentElement.dir = nextLanguage === "ar" ? "rtl" : "ltr";
    setCurrentLanguage(nextLanguage);

    try {
      window.localStorage?.setItem(STORAGE_KEY, nextLanguage);
    } catch {
      // Ignore storage failures in restricted browser environments.
    }

    window.location.reload();
  };

  const t = (text: string) => {
    const translated = language === "en" ? text : translations[text] || text;
    return sanitizeProductNames(language, translated);
  };

  const safeText = (text: string) => text;

  return (
    <I18nContext.Provider
      value={{
        language,
        dir: language === "ar" ? "rtl" : "ltr",
        setLanguage,
        t,
        safeText,
      }}
    >
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);

  if (!context) {
    throw new Error("useI18n must be used inside LanguageProvider");
  }

  return context;
}
