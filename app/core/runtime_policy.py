SAFE_RUNTIME_TOOLSETS = ["skills", "vision", "clarify", "todo"]

PROHIBITED_RUNTIME_TOOLSETS = frozenset({"terminal", "code_execution"})

ALL_RUNTIME_TOOLSETS = frozenset({
    "web", "browser", "terminal", "file", "code_execution", "vision", "video",
    "image_gen", "video_gen", "x_search", "tts", "skills", "todo", "memory",
    "context_engine", "session_search", "clarify", "delegation", "cronjob",
    "homeassistant", "spotify", "discord", "discord_admin", "yuanbao",
    "computer_use",
})

RUNTIME_TOOLSETS = ALL_RUNTIME_TOOLSETS - PROHIBITED_RUNTIME_TOOLSETS


def normalize_runtime_toolsets(toolsets: list[str] | None) -> list[str]:
    values = SAFE_RUNTIME_TOOLSETS if toolsets is None else toolsets
    normalized = list(dict.fromkeys(item.strip() for item in values if item and item.strip()))
    prohibited = sorted(set(normalized) & PROHIBITED_RUNTIME_TOOLSETS)
    if prohibited:
        raise ValueError(f"Prohibited runtime toolsets: {', '.join(prohibited)}")
    unknown = sorted(set(normalized) - RUNTIME_TOOLSETS)
    if unknown:
        raise ValueError(f"Unsupported runtime toolsets: {', '.join(unknown)}")
    return normalized


def effective_profile_policy(profile) -> dict:
    """Return the non-secret policy contract enforced for a profile."""
    version = int(getattr(profile, "version", 1) or 1)
    return {
        "version": version,
        "policy_id": f"profile-{getattr(profile, 'id', 'unknown')}-v{version}",
        "runtime_type": str(getattr(profile, "runtime_type", "hermes") or "hermes"),
        "runtime_toolsets": normalize_runtime_toolsets(getattr(profile, "runtime_toolsets", None)),
        "prohibited_toolsets": sorted(PROHIBITED_RUNTIME_TOOLSETS),
        "allowed_tools": list(dict.fromkeys(getattr(profile, "allowed_tools", None) or [])),
        "approval_required_tools": list(
            dict.fromkeys(getattr(profile, "approval_required_tools", None) or [])
        ),
    }
