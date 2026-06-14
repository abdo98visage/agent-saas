"""Desktop hardening regression checks."""


def test_renderer_has_offline_queue_and_preview_controls():
    with open("desktop/src/renderer/index.html") as file:
        content = file.read()

    assert "offlineQueue" in content
    assert "flushQueuedMessages" in content
    assert "btn-prepare-write" in content
    assert "btn-apply-write" in content
    assert "queue-badge" in content


def test_main_process_has_workspace_path_restrictions():
    with open("desktop/src/main/main.js") as file:
        content = file.read()

    assert "File path escapes the selected workspace" in content
    assert "resolveWorkspaceFile" in content
    assert "setWindowOpenHandler" in content
    assert "will-navigate" in content


def test_main_process_uses_context_snippets_not_full_scan_payloads():
    with open("desktop/src/main/main.js") as file:
        content = file.read()

    assert "MAX_CONTEXT_TOTAL_CHARS" in content
    assert "MAX_CONTEXT_FILE_CHARS" in content
    assert "snippet" in content
    assert "build-project-context" in content


def test_preload_exposes_reviewed_write_flow():
    with open("desktop/src/preload/preload.js") as file:
        content = file.read()

    assert "prepareFileWrite" in content
    assert "applyFileWrite" in content
    assert "buildProjectContext" in content
