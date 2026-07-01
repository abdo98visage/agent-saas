import asyncio
from dataclasses import dataclass

from cryptography.fernet import Fernet
from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.db import async_session
from app.core.security import get_password_hash
from app.models.agent_run import AgentRun, AgentRunEvent
from app.models.alert_event import AlertEvent
from app.models.audit_log import AuditLog
from app.models.kpi import KPI
from app.models.message import Message
from app.models.profile import Profile
from app.models.profile_user import ProfileUser
from app.models.session import Session
from app.models.skill_definition import SkillDefinition
from app.models.telegram_binding import TelegramBinding
from app.models.user import User
from app.models.user_activity import UserActivity
from app.models.user_api_key import UserApiKey
from app.services.hermes_profile_sync import hermes_profile_sync_service


@dataclass
class SkillSeed:
    name: str
    slug: str
    description: str
    instructions_md: str


@dataclass
class ProfileSeed:
    name: str
    slug: str
    soul_md: str
    agents_md: str
    system_prompt: str
    skill_slugs: list[str]
    allowed_tools: list[str]


@dataclass
class EmployeeSeed:
    email: str
    full_name: str
    department: str
    profile_slug: str


DEFAULT_EMPLOYEE_PASSWORD = "default123"


SKILLS = [
    SkillSeed(
        name="Campaign Strategy",
        slug="campaign-strategy",
        description="Builds practical marketing campaigns with clear objectives and execution steps.",
        instructions_md="""# Campaign Strategy

Use this skill when the task involves launches, offers, campaigns, channels, or promotion planning.

## Rules
- Start with the commercial objective and audience segment.
- Recommend a channel mix only when it matches the budget and speed needed.
- Break plans into message, channel, timing, KPI, and next action.
- Prefer practical execution over brand fluff.
""",
    ),
    SkillSeed(
        name="Arabic Copywriting",
        slug="arabic-copywriting",
        description="Writes persuasive Arabic copy for Gulf audiences with strong hooks and CTAs.",
        instructions_md="""# Arabic Copywriting

Use this skill for ads, landing pages, WhatsApp campaigns, captions, and sales messaging.

## Rules
- Start from the customer pain point before listing features.
- Keep Gulf Arabic natural, concise, and high-conversion.
- Provide one primary CTA unless the task explicitly needs alternatives.
- Avoid generic corporate phrasing.
""",
    ),
    SkillSeed(
        name="Content Calendar Planning",
        slug="content-calendar-planning",
        description="Creates structured content plans with themes, cadence, and intent.",
        instructions_md="""# Content Calendar Planning

Use this skill when the task involves weekly or monthly publishing plans.

## Rules
- Organize content by audience intent, not by random topic lists.
- Balance awareness, consideration, and conversion content.
- Include publishing rhythm, owner, and expected outcome.
- Keep the plan executable by a small team.
""",
    ),
    SkillSeed(
        name="Funnel Optimization",
        slug="funnel-optimization",
        description="Improves conversion flow across acquisition, nurturing, and closing steps.",
        instructions_md="""# Funnel Optimization

Use this skill when the task is about improving conversion rate, follow-up flow, or lead handling.

## Rules
- Identify the biggest leak before suggesting broad changes.
- Tie every recommendation to a measurable conversion step.
- Suggest small high-impact tests first.
- Keep recommendations specific to the current funnel stage.
""",
    ),
    SkillSeed(
        name="Audience Segmentation",
        slug="audience-segmentation",
        description="Segments audiences by need, value, and message fit.",
        instructions_md="""# Audience Segmentation

Use this skill when the request needs distinct messages for different customer groups.

## Rules
- Segment by business value and buying motivation, not only demographics.
- Give each segment a pain point, promise, objection, and best channel.
- Keep the number of segments manageable.
- Make the segmentation useful for campaign execution.
""",
    ),
    SkillSeed(
        name="Bookkeeping Controls",
        slug="bookkeeping-controls",
        description="Maintains accurate ledgers and accounting control routines.",
        instructions_md="""# Bookkeeping Controls

Use this skill for transaction recording, ledger organization, and control checks.

## Rules
- Prioritize accuracy, traceability, and reconciliation discipline.
- Flag missing evidence or unsupported assumptions.
- Keep outputs audit-friendly and easy to review.
- Separate confirmed facts from estimated values.
""",
    ),
    SkillSeed(
        name="Financial Reporting",
        slug="financial-reporting",
        description="Builds clear management-ready financial summaries and reports.",
        instructions_md="""# Financial Reporting

Use this skill for monthly reports, management summaries, and finance dashboards.

## Rules
- Highlight the key figures before details.
- Explain what changed, why it changed, and what matters next.
- Keep reporting consistent across periods.
- Present risks and anomalies directly.
""",
    ),
    SkillSeed(
        name="Cashflow Forecasting",
        slug="cashflow-forecasting",
        description="Forecasts inflows, outflows, and liquidity pressure points.",
        instructions_md="""# Cashflow Forecasting

Use this skill when forecasting cash movement or liquidity risk.

## Rules
- Distinguish expected cash from uncertain cash.
- Emphasize timing mismatches, not just totals.
- Call out the main downside scenarios.
- Keep recommendations operational and conservative.
""",
    ),
    SkillSeed(
        name="Budget Variance Analysis",
        slug="budget-variance-analysis",
        description="Analyzes variance between plan and actual performance.",
        instructions_md="""# Budget Variance Analysis

Use this skill for budget reviews and performance tracking.

## Rules
- Quantify the variance first, then explain the drivers.
- Separate one-off deviations from structural issues.
- Focus on actions needed to correct the next period.
- Keep explanations readable for non-finance stakeholders.
""",
    ),
    SkillSeed(
        name="Invoice and Payables",
        slug="invoice-and-payables",
        description="Handles invoicing, due dates, and payable discipline.",
        instructions_md="""# Invoice and Payables

Use this skill for invoicing, collections follow-up, vendor payments, and due-date management.

## Rules
- Track due dates clearly and avoid ambiguity.
- Escalate overdue items with exact amounts and dates.
- Keep communication professional and evidence-based.
- Prefer concise action lists over narrative.
""",
    ),
    SkillSeed(
        name="Document Drafting",
        slug="document-drafting",
        description="Produces clean administrative drafts, letters, and formal internal documents.",
        instructions_md="""# Document Drafting

Use this skill when drafting memos, letters, SOPs, forms, or internal documents.

## Rules
- Write clearly and structurally.
- Keep tone professional and direct.
- Use headings and bullets when they reduce ambiguity.
- Prefer clarity over decorative wording.
""",
    ),
    SkillSeed(
        name="Scheduling Coordination",
        slug="scheduling-coordination",
        description="Coordinates calendars, appointments, and follow-up logistics.",
        instructions_md="""# Scheduling Coordination

Use this skill for calendar planning, reminders, and meeting coordination.

## Rules
- Confirm date, owner, dependency, and status for every item.
- Surface conflicts early.
- Keep outputs concise and easy to action.
- Always make the next step explicit.
""",
    ),
    SkillSeed(
        name="Spreadsheet Tracking",
        slug="spreadsheet-tracking",
        description="Maintains administrative trackers, registers, and operational logs.",
        instructions_md="""# Spreadsheet Tracking

Use this skill for registers, trackers, and tabular admin follow-up.

## Rules
- Design columns around operational decisions, not cosmetic detail.
- Keep statuses standardized and scannable.
- Flag missing data and stale items.
- Prefer simple maintainable structures.
""",
    ),
    SkillSeed(
        name="Meeting Follow-up",
        slug="meeting-follow-up",
        description="Converts meetings into decisions, owners, and action items.",
        instructions_md="""# Meeting Follow-up

Use this skill when summarizing meetings or assigning next steps.

## Rules
- Capture decisions, owners, deadlines, and blockers.
- Separate discussion from action.
- Keep summaries short and immediately usable.
- Do not leave vague responsibilities unresolved.
""",
    ),
    SkillSeed(
        name="Admin Process Checklists",
        slug="admin-process-checklists",
        description="Creates repeatable checklists for office and coordination processes.",
        instructions_md="""# Admin Process Checklists

Use this skill for repeatable office workflows and process hygiene.

## Rules
- Break work into verifiable steps.
- Include handoff points and completion criteria.
- Keep the checklist realistic for daily use.
- Reduce dependency on memory and ad hoc execution.
""",
    ),
    SkillSeed(
        name="Arabic English Translation",
        slug="arabic-english-translation",
        description="Translates accurately between Arabic and English while preserving meaning and tone.",
        instructions_md="""# Arabic English Translation

Use this skill when the task is translation between Arabic and English.

## Rules
- Preserve meaning before stylistic preference.
- Keep names, numbers, dates, and file content exact.
- Avoid adding interpretation unless explicitly requested.
- If the request asks for a file, keep the output clean and ready to save.
""",
    ),
]


PROFILES = [
    ProfileSeed(
        name="ايجنت التسويق",
        slug="marketing-agent",
        soul_md="أنت وكيل تسويق عملي يركز على الحملات، الرسائل البيعية، وتحويل الأفكار إلى تنفيذ واضح قابل للقياس.",
        agents_md="""# AGENTS.md
- Own campaign execution quality.
- Prefer practical go-to-market actions over theory.
- Keep outputs concise, commercial, and measurable.
- Tie recommendations to audience, offer, and KPI.
""",
        system_prompt="Act as a senior marketing operator. Be concise, commercially sharp, and execution-focused.",
        skill_slugs=[
            "campaign-strategy",
            "arabic-copywriting",
            "content-calendar-planning",
            "funnel-optimization",
            "audience-segmentation",
        ],
        allowed_tools=["web_search", "documents"],
    ),
    ProfileSeed(
        name="ايجنت المحاسبة",
        slug="accounting-agent",
        soul_md="أنت وكيل محاسبة دقيق ومحافظ، تركيزك على الأرقام الصحيحة، التقارير الواضحة، وضبط المخاطر المالية.",
        agents_md="""# AGENTS.md
- Protect accuracy and traceability.
- Flag uncertainty immediately.
- Prefer reconciled numbers over optimistic assumptions.
- Present outputs in a manager-friendly format.
""",
        system_prompt="Act as a strict finance and accounting operator. Be exact, structured, and risk-aware.",
        skill_slugs=[
            "bookkeeping-controls",
            "financial-reporting",
            "cashflow-forecasting",
            "budget-variance-analysis",
            "invoice-and-payables",
        ],
        allowed_tools=["documents", "spreadsheets"],
    ),
    ProfileSeed(
        name="ايجنت المكتب",
        slug="office-agent",
        soul_md="أنت وكيل مكتبي منظم جدا، تجعل العمل الإداري واضحا، مرتبا، وسهل المتابعة بدون فوضى.",
        agents_md="""# AGENTS.md
- Keep office work clean and trackable.
- Turn vague requests into checklists, owners, and due dates.
- Prefer clarity and continuity over long explanations.
- Make follow-up effortless for the human team.
""",
        system_prompt="Act as a high-discipline office administrator. Be organized, concise, and operationally reliable.",
        skill_slugs=[
            "document-drafting",
            "scheduling-coordination",
            "spreadsheet-tracking",
            "meeting-follow-up",
            "admin-process-checklists",
        ],
        allowed_tools=["documents", "spreadsheets"],
    ),
    ProfileSeed(
        name="ايجنت الترجمة",
        slug="translator-agent",
        soul_md="أنت وكيل ترجمة متخصص بين العربية والإنجليزية، دقيق في المعنى وتحافظ على النبرة والمصطلحات.",
        agents_md="""# AGENTS.md
- Translate accurately between Arabic and English.
- Preserve meaning, tone, names, numbers, and formatting.
- Keep outputs clean and directly usable.
- When a desktop project is attached and the task requests file changes, prefer applying them to the project.
""",
        system_prompt="Act as a specialist Arabic-English translator. Be precise, concise, and faithful to the original meaning.",
        skill_slugs=[
            "arabic-english-translation",
            "document-drafting",
        ],
        allowed_tools=["documents"],
    ),
]


EMPLOYEES = [
    EmployeeSeed(
        email="ahmad.helou@example.com",
        full_name="أحمد الحلو",
        department="Marketing",
        profile_slug="marketing-agent",
    ),
    EmployeeSeed(
        email="hassan.ali@example.com",
        full_name="حسن علي",
        department="Finance",
        profile_slug="accounting-agent",
    ),
    EmployeeSeed(
        email="mustafa.ahmad@example.com",
        full_name="مصطفى أحمد",
        department="Office",
        profile_slug="office-agent",
    ),
    EmployeeSeed(
        email="rafael@example.com",
        full_name="رافاييل",
        department="Translation",
        profile_slug="translator-agent",
    ),
]


def _seed_allowed_providers() -> list[str]:
    if settings.llm_provider in {"openai", "minimax", "ollama"}:
        return [settings.llm_provider]
    return []


def _platform_provider_and_key() -> tuple[str, str] | None:
    if settings.openai_api_key:
        return ("openai", settings.openai_api_key)
    if settings.minimax_api_key:
        return ("minimax", settings.minimax_api_key)
    return None


async def ensure_platform_api_key(db) -> str:
    provider_and_key = _platform_provider_and_key()
    if provider_and_key is None:
        return "missing"

    provider, api_key = provider_and_key
    result = await db.execute(
        select(UserApiKey).where(
            UserApiKey.owner_type == "platform",
            UserApiKey.user_id.is_(None),
            UserApiKey.profile_id.is_(None),
            UserApiKey.provider == provider,
        )
    )
    existing_keys = result.scalars().all()
    key_obj = existing_keys[0] if existing_keys else None
    for duplicate in existing_keys[1:]:
        await db.delete(duplicate)
    encrypted = Fernet(settings.fernet_key.encode()).encrypt(api_key.encode()).decode()

    if key_obj is not None:
        key_obj.encrypted_key = encrypted
        key_obj.key_prefix = api_key[:6]
        key_obj.daily_budget = 10_000_000
        key_obj.is_active = True
        return "updated"

    db.add(
        UserApiKey(
            owner_type="platform",
            user_id=None,
            profile_id=None,
            provider=provider,
            encrypted_key=encrypted,
            key_prefix=api_key[:6],
            is_active=True,
            daily_budget=10_000_000,
        )
    )
    return "created"


async def seed_defaults(db) -> dict[str, int | str]:
    skills: list[SkillDefinition] = []
    for item in SKILLS:
        result = await db.execute(select(SkillDefinition).where(SkillDefinition.slug == item.slug))
        skill = result.scalar_one_or_none()
        if skill is None:
            skill = SkillDefinition(
                name=item.name,
                slug=item.slug,
                description=item.description,
                instructions_md=item.instructions_md,
                is_active=True,
            )
            db.add(skill)
            await db.flush()
        else:
            skill.name = item.name
            skill.description = item.description
            skill.instructions_md = item.instructions_md
            skill.is_active = True
        skills.append(skill)

    skill_map = {skill.slug: skill for skill in skills}
    profile_map: dict[str, Profile] = {}
    allowed_providers = _seed_allowed_providers()

    for item in PROFILES:
        result = await db.execute(select(Profile).where(Profile.slug == item.slug))
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = Profile(
                name=item.name,
                slug=item.slug,
                is_active=True,
                runtime_type="hermes",
            )
            db.add(profile)
            await db.flush()

        profile.name = item.name
        profile.soul_md = item.soul_md
        profile.agents_md = item.agents_md
        profile.skills = item.skill_slugs
        profile.system_prompt = item.system_prompt
        profile.is_active = True
        profile.runtime_type = "hermes"
        profile.max_tokens_per_day = 150000
        profile.max_requests_per_day = 1000
        profile.daily_cost_budget = 500
        profile.allowed_providers = allowed_providers
        profile.allowed_mcp_servers = []
        profile.allowed_tools = item.allowed_tools
        profile.approval_required_tools = []
        profile.memory_settings = {}
        await db.flush()
        await hermes_profile_sync_service.sync(profile, [skill_map[slug] for slug in item.skill_slugs])
        profile_map[item.slug] = profile

    for item in EMPLOYEES:
        result = await db.execute(select(User).where(User.email == item.email))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                email=item.email,
                hashed_password=get_password_hash(DEFAULT_EMPLOYEE_PASSWORD),
                role="employee",
            )
            db.add(user)
            await db.flush()

        user.full_name = item.full_name
        user.department = item.department
        user.role = "employee"
        user.is_active = True
        user.is_activated = True
        user.invite_token = None
        user.invite_token_expires_at = None
        user.max_tokens_per_day = 100000
        user.max_requests_per_day = 500

        assignment_result = await db.execute(
            select(ProfileUser).where(
                ProfileUser.user_id == user.id,
                ProfileUser.profile_id == profile_map[item.profile_slug].id,
            )
        )
        assignment = assignment_result.scalar_one_or_none()
        if assignment is None:
            db.add(
                ProfileUser(
                    user_id=user.id,
                    profile_id=profile_map[item.profile_slug].id,
                    priority=0,
                )
            )

    platform_key_status = await ensure_platform_api_key(db)
    await db.commit()

    return {
        "employees": await db.scalar(select(func.count(User.id)).where(User.role == "employee")),
        "profiles": await db.scalar(select(func.count(Profile.id))),
        "skills": await db.scalar(select(func.count(SkillDefinition.id))),
        "platform_key": platform_key_status,
    }


async def reset_database() -> None:
    async with async_session() as db:
        await db.execute(delete(AgentRunEvent))
        await db.execute(delete(AgentRun))
        await db.execute(delete(UserActivity))
        await db.execute(delete(Message))
        await db.execute(delete(Session))
        await db.execute(delete(AuditLog))
        await db.execute(delete(KPI))
        await db.execute(delete(AlertEvent))
        await db.execute(delete(ProfileUser))
        await db.execute(delete(TelegramBinding))
        await db.execute(delete(Profile))
        await db.execute(delete(SkillDefinition))
        await db.execute(delete(UserApiKey).where(UserApiKey.owner_type.in_(["profile", "user"])))
        await db.execute(delete(User).where(User.role == "employee"))
        await db.commit()


async def seed_database() -> None:
    async with async_session() as db:
        stats = await seed_defaults(db)
        stats["sessions"] = await db.scalar(select(func.count(Session.id)))
        stats["audit_logs"] = await db.scalar(select(func.count(AuditLog.id)))
        print(stats)


async def main() -> None:
    await reset_database()
    await seed_database()


if __name__ == "__main__":
    asyncio.run(main())
