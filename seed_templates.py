"""
Seed script: create default agent templates and the admin user.
Run: python seed_templates.py
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    from asyncio import WindowsSelectorEventLoopPolicy

    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.db import Base
from app.core.security import create_access_token, get_password_hash
from app.models.agent_template import AgentTemplate
from app.models.skill_definition import SkillDefinition
from app.models.user import User
from scripts.reset_seed_clean_workspace import (
    DEFAULT_EMPLOYEE_PASSWORD,
    EMPLOYEES,
    PROFILES,
    seed_defaults,
)


DEFAULT_TEMPLATES = [
    {
        "name": "default",
        "department": None,
        "system_prompt": "You are a helpful AI assistant. Be professional, clear, and concise.",
        "model_name": settings.default_model,
        "temperature": 0.7,
        "max_tokens_per_request": 4000,
        "tools": ["web_search"],
    },
    {
        "name": "it",
        "department": "it",
        "system_prompt": "You are an IT expert. Help with code, debugging, architecture, and technical documentation.",
        "model_name": settings.default_model,
        "temperature": 0.3,
        "max_tokens_per_request": 8000,
        "tools": ["code_search", "file_read", "file_write", "command_runner"],
    },
    {
        "name": "marketing",
        "department": "marketing",
        "system_prompt": "You are a marketing specialist. Help with campaigns, content creation, SEO, and social media.",
        "model_name": settings.default_model,
        "temperature": 0.8,
        "max_tokens_per_request": 4000,
        "tools": ["content_generator", "web_search", "competitor_analyzer"],
    },
    {
        "name": "hr",
        "department": "hr",
        "system_prompt": "You are an HR professional. Help with employee management, policies, and recruitment.",
        "model_name": settings.default_model,
        "temperature": 0.5,
        "max_tokens_per_request": 4000,
        "tools": ["web_search"],
    },
]

DEFAULT_SKILLS = [
    {
        "name": "Campaigns",
        "slug": "campaigns",
        "description": "Marketing campaign planning and execution.",
        "instructions_md": "# Campaigns\n\nPlan and optimize marketing campaigns.",
        "is_active": True,
    },
    {
        "name": "Copywriting",
        "slug": "copywriting",
        "description": "Marketing copywriting for ads and landing pages.",
        "instructions_md": "# Copywriting\n\nWrite concise, high-conversion marketing copy.",
        "is_active": True,
    },
]


async def seed() -> None:
    print("=" * 50)
    print("  FQ-SaaS Seed Script")
    print("=" * 50)
    print()

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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
            _ = create_access_token(str(admin.id), "admin")
            print(f"  [ok] Admin user created: {admin_email}")
            print(f"       Password: {admin_password}")
        else:
            print(f"  [skip] Admin user exists: {admin_email}")

        for tmpl in DEFAULT_TEMPLATES:
            existing = await session.execute(select(AgentTemplate).where(AgentTemplate.name == tmpl["name"]))
            if existing.scalar_one_or_none():
                print(f"  [skip] Template exists: {tmpl['name']}")
                continue
            session.add(AgentTemplate(**tmpl))
            print(f"  [ok] Template: {tmpl['name']}")

        for skill_data in DEFAULT_SKILLS:
            existing = await session.execute(
                select(SkillDefinition).where(SkillDefinition.slug == skill_data["slug"])
            )
            if existing.scalar_one_or_none():
                print(f"  [skip] Skill exists: {skill_data['slug']}")
                continue
            session.add(SkillDefinition(**skill_data))
            print(f"  [ok] Skill: {skill_data['slug']}")

        await session.commit()
        seed_stats = await seed_defaults(session)
        print(
            "  [ok] Default workspace seeded:"
            f" {seed_stats['profiles']} profiles,"
            f" {seed_stats['employees']} employees,"
            f" password={DEFAULT_EMPLOYEE_PASSWORD}"
        )
        print(
            "  [info] Profiles: "
            + ", ".join(profile.slug for profile in PROFILES)
        )
        print(
            "  [info] Employees: "
            + ", ".join(employee.email for employee in EMPLOYEES)
        )

    print()
    print("=" * 50)
    print("  Seeding complete")
    print("=" * 50)
    print()
    print("  Login: http://localhost:3000/login")
    print(f"  Email: {admin_email}")
    print(f"  Password: {admin_password}")
    print()


if __name__ == "__main__":
    asyncio.run(seed())
