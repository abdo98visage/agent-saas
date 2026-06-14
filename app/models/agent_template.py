from sqlalchemy import String, Float, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class AgentTemplate(Base):
    __tablename__ = "agent_templates"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    department: Mapped[str] = mapped_column(String(50), nullable=True)
    system_prompt: Mapped[str] = mapped_column(nullable=False)
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    model_name: Mapped[str] = mapped_column(String(50), default="qwen3-14b")
    max_tokens_per_request: Mapped[int] = mapped_column(Integer, default=4000)
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
