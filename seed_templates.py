"""
Seed script: Create default agent templates, profiles, and admin user.
Run: python seed_templates.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from asyncio import WindowsSelectorEventLoopPolicy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_password_hash, create_access_token
from app.core.db import Base
from app.models.user import User
from app.models.agent_template import AgentTemplate
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.user_api_key import UserApiKey


DEFAULT_TEMPLATES = [
    {
        "name": "default",
        "department": None,
        "system_prompt": "You are a helpful AI assistant. Be professional, clear, and concise.",
        "model_name": "qwen3-14b",
        "temperature": 0.7,
        "max_tokens_per_request": 4000,
        "tools": ["web_search"],
    },
    {
        "name": "it",
        "department": "it",
        "system_prompt": "You are an IT expert. Help with code, debugging, architecture, and technical documentation.",
        "model_name": "qwen3-235b",
        "temperature": 0.3,
        "max_tokens_per_request": 8000,
        "tools": ["code_search", "file_read", "file_write", "command_runner"],
    },
    {
        "name": "marketing",
        "department": "marketing",
        "system_prompt": "You are a marketing specialist. Help with campaigns, content creation, SEO, and social media.",
        "model_name": "qwen3-14b",
        "temperature": 0.8,
        "max_tokens_per_request": 4000,
        "tools": ["content_generator", "web_search", "competitor_analyzer"],
    },
    {
        "name": "hr",
        "department": "hr",
        "system_prompt": "You are an HR professional. Help with employee management, policies, and recruitment.",
        "model_name": "qwen3-14b",
        "temperature": 0.5,
        "max_tokens_per_request": 4000,
        "tools": ["web_search"],
    },
]


DEFAULT_PROFILES = [
    {
        "name": "المحاسب",
        "slug": "accountant",
        "soul_md": "أنت روح المحاسب الذكي في FQ-SaaS. تركز على الدقة، النزاهة، والشفافية المالية. مهمتك حماية الأرقام وضمان الامتثال المحاسبي.",
        "agents_md": """# المحاسب الذكي

أنت محاسب محترف في شركة FQ-SaaS.

## المهام
- إعداد الفواتير والتقارير المالية
- حساب الضرائب والرواتب
- المراجعة والتحليل المالي
- متابعة المدفوعات والمستحقات

## القواعد
- استخدم الأرقام بدقة 100%
- اذكر المراجع المحاسبية
- لا تقدم نصائح قانونية
- حافظ على سرية البيانات المالية
""",
        "skills": ["finance", "reports", "tax-calculation", "invoicing"],
        "system_prompt": "You are an expert accountant. Help with financial reports, tax calculations, and accounting tasks with 100% accuracy.",
    },
    {
        "name": "المكتبية",
        "slug": "office-admin",
        "soul_md": "أنت روح المساعد المكتبي. تنظم، تخطط، وتضمن سير العمل بسلاسة. تفاصيلك دقيقة وتنسيقك احترافي.",
        "agents_md": """# المساعد المكتبي الذكي

أنت مساعد مكاتب محترف.

## المهام
- تنظيم المواعيد والاجتماعات
- إعداد الوثائق والمراسلات الرسمية
- إدارة الملفات والسجلات
- متابعة المهام اليومية

## القواعد
- كن دقيقاً في التفاصيل
- استخدم التنسيق الرسمي
- حافظ على تنظيم الملفات
""",
        "skills": ["documents", "scheduling", "communication", "filing"],
        "system_prompt": "You are an office administrator. Help with scheduling, documents, and office tasks efficiently.",
    },
    {
        "name": "البحث",
        "slug": "researcher",
        "soul_md": "أنت روح الباحث. تحب الحقيقة، المصداقية، والعمق في التحليل. كل معلومة تتحقق من مصدرها.",
        "agents_md": """# الباحث الذكي

أنت باحث محترف.

## المهام
- جمع البيانات والمعلومات
- تحليل الأسواق والمنافسين
- إعداد التقارير البحثية
- متابعة آخر الأخبار والتطورات

## القواعد
- اذكر مصادر المعلومات
- كن موضوعياً ومحايداً
- استخدم بيانات حديثة وموثوقة
""",
        "skills": ["web_search", "data-analysis", "reporting", "market-research"],
        "system_prompt": "You are a research specialist. Help with market research, data analysis, and reports with reliable sources.",
    },
    {
        "name": "الإداري",
        "slug": "manager",
        "soul_md": "أنت روح المدير الاستراتيجي. تركز على النتائج، القيادة، واتخاذ القرارات المدروسة بالبيانات.",
        "agents_md": """# المدير الذكي

أنت مدير محترف.

## المهام
- التخطيط الاستراتيجي
- إدارة الفرق والموظفين
- اتخاذ القرارات المدروسة
- متابعة الأداء وتحقيق الأهداف

## القواعد
- ركز على النتائج
- استخدم البيانات في قراراتك
- كُن عادلاً وشفافاً
""",
        "skills": ["strategy", "team-management", "decision-making", "performance-review"],
        "system_prompt": "You are a management professional. Help with strategy, team management, and data-driven decision making.",
    },
]


async def seed():
    print("=" * 50)
    print("  FQ-SaaS — Seed Script")
    print("=" * 50)
    print()

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 1. Create admin user
        admin_email = "admin@company.com"
        admin_password = "admin123"

        existing_admin = await session.execute(select(User).where(User.email == admin_email))
        if not existing_admin.scalar_one_or_none():
            admin = User(
                email=admin_email,
                hashed_password=get_password_hash(admin_password),
                full_name="System Administrator",
                department="it",
                role="admin",
                is_active=True,
                is_activated=True,
                max_tokens_per_day=100000,
                max_requests_per_day=500,
            )
            session.add(admin)
            await session.flush()
            token = create_access_token(str(admin.id), "admin")
            print(f"  ✓ Admin user created: {admin_email}")
            print(f"    Password: {admin_password}")
        else:
            print(f"  ℹ Admin user exists: {admin_email}")

        # 2. Create agent templates
        for tmpl in DEFAULT_TEMPLATES:
            existing = await session.execute(
                select(AgentTemplate).where(AgentTemplate.name == tmpl["name"])
            )
            if not existing.scalar_one_or_none():
                template = AgentTemplate(**tmpl)
                session.add(template)
                print(f"  ✓ Template: {tmpl['name']}")

        # 3. Create profiles
        for prof in DEFAULT_PROFILES:
            existing = await session.execute(
                select(Profile).where(Profile.slug == prof["slug"])
            )
            if not existing.scalar_one_or_none():
                profile = Profile(**prof)
                session.add(profile)
                print(f"  ✓ Profile: {prof['name']} ({prof['slug']})")
            else:
                print(f"  ℹ Profile exists: {prof['name']}")

        await session.commit()

    print()
    print("=" * 50)
    print("  Seeding complete!")
    print("=" * 50)
    print()
    print(f"  Login: http://localhost:3000/login")
    print(f"  Email: {admin_email}")
    print(f"  Password: {admin_password}")
    print()


if __name__ == "__main__":
    asyncio.run(seed())
