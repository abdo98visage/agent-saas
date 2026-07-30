SAFE_RUNTIME_TOOLSETS = ["skills", "vision", "clarify", "todo"]

RUNTIME_TOOLSETS = frozenset({
    "web", "browser", "terminal", "file", "code_execution", "vision", "video",
    "image_gen", "video_gen", "x_search", "tts", "skills", "todo", "memory",
    "context_engine", "session_search", "clarify", "delegation", "cronjob",
    "homeassistant", "spotify", "discord", "discord_admin", "yuanbao",
    "computer_use",
})


def normalize_runtime_toolsets(toolsets: list[str] | None) -> list[str]:
    values = SAFE_RUNTIME_TOOLSETS if toolsets is None else toolsets
    normalized = list(dict.fromkeys(item.strip() for item in values if item and item.strip()))
    unknown = sorted(set(normalized) - RUNTIME_TOOLSETS)
    if unknown:
        raise ValueError(f"Unsupported runtime toolsets: {', '.join(unknown)}")
    return normalized
