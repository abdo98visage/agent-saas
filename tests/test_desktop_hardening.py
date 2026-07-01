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
    assert "setPermissionRequestHandler" in content
    assert "Content-Security-Policy" in content


def test_main_process_uses_context_snippets_not_full_scan_payloads():
    with open("desktop/src/main/main.js") as file:
        content = file.read()

    assert "MAX_CONTEXT_TOTAL_CHARS" in content
    assert "MAX_CONTEXT_FILE_CHARS" in content
    assert "snippet" in content
    assert "build-project-context" in content
    assert "EXCLUDED_FILE_PREFIXES" in content
    assert "EXCLUDED_FILE_EXTENSIONS" in content
    assert "SECRET_FILE_PATTERNS" in content


def test_preload_exposes_reviewed_write_flow():
    with open("desktop/src/preload/preload.js") as file:
        content = file.read()

    assert "prepareFileWrite" in content
    assert "applyFileWrite" in content
    assert "buildProjectContext" in content
    assert "prepareWorkspaceChanges" in content
    assert "applyWorkspaceChanges" in content
    assert "readMultipleFiles" in content
    assert "searchFiles" in content
    assert "saveConversationArtifact" in content


def test_renderer_uses_local_assets_and_csp():
    with open("desktop/src/renderer/index.html") as file:
        content = file.read()

    assert "Content-Security-Policy" in content
    assert "vendor.css" in content
    assert "cdn.jsdelivr" not in content
    assert "fonts.googleapis" not in content


def test_desktop_has_update_feed_hook():
    with open("desktop/src/main/main.js") as file:
        main_content = file.read()
    with open("desktop/package.json") as file:
        package_content = file.read()
    with open("desktop/src/preload/preload.js") as file:
        preload_content = file.read()
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        renderer_content = file.read()

    assert "UPDATE_FEED_URL" in main_content
    assert "autoUpdater" in main_content
    assert "check-for-updates" in main_content
    assert "get-update-status" in main_content
    assert "checkForUpdates" in preload_content
    assert "getUpdateStatus" in preload_content
    assert "btn-check-updates" in renderer_content
    assert "update-status" in renderer_content
    assert '"electron": "^42.4.0"' in package_content
    assert '"electron-builder": "^26.15.3"' in package_content
    assert '"publish"' not in package_content
    assert "requiredForRelease.push(\"UPDATE_FEED_URL is not set.\")" in open("desktop/scripts/release-check.js", encoding="utf-8").read()
    assert "ALLOW_INSECURE_DESKTOP_RELEASE" in open("desktop/scripts/release-check.js", encoding="utf-8").read()
    assert "Desktop release API URL still points to localhost." in open("desktop/scripts/release-check.js", encoding="utf-8").read()


def test_desktop_supports_generic_activation_links():
    with open("desktop/src/main/main.js", encoding="utf-8") as file:
        main_content = file.read()
    with open("desktop/src/preload/preload.js", encoding="utf-8") as file:
        preload_content = file.read()
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        renderer_content = file.read()

    assert "ACTIVATION_PROTOCOL = \"fqsaas\"" in main_content
    assert "setAsDefaultProtocolClient(ACTIVATION_PROTOCOL)" in main_content
    assert "parseActivationUrl" in main_content
    assert "activationToken" in main_content
    assert "onActivationLink" in preload_content
    assert "applyActivationSettings" in renderer_content
    assert "activationApiUrl" in renderer_content


def test_desktop_main_process_has_local_cowork_tools():
    with open("desktop/src/main/main.js", encoding="utf-8") as file:
        content = file.read()

    assert "listWorkspaceFiles" in content
    assert "searchWorkspaceFiles" in content
    assert "readMultipleWorkspaceFiles" in content
    assert "prepareWorkspaceChanges" in content
    assert "applyWorkspaceChanges" in content
    assert "save-conversation-artifact" in content
    assert "KarzounOS" in content


def test_desktop_saves_conversation_artifacts_under_system_downloads():
    with open("desktop/src/main/main.js", encoding="utf-8") as file:
        content = file.read()

    assert 'app.getPath("downloads")' in content
    assert 'path.join(downloadsRoot, "KarzounOS")' in content
    assert 'path.join(os.homedir(), "Downloads")' in content


def test_desktop_workspace_writes_are_applied_inside_selected_project():
    with open("desktop/src/main/main.js", encoding="utf-8") as file:
        main_content = file.read()
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        renderer_content = file.read()

    assert "resolveWorkspaceFile(rootPath" in main_content
    assert "prepareWorkspaceChanges(rootPath, changes = [])" in main_content
    assert "applyWorkspaceChanges(previewToken)" in main_content
    assert "window.electronAPI.prepareWorkspaceChanges(state.projectPath, data.changes || [])" in renderer_content
    assert "window.electronAPI.applyWorkspaceChanges(preview.previewToken)" in renderer_content


def test_renderer_inline_artifact_parser_supports_section_format():
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        content = file.read()

    assert "(?:Filename|اسم الملف)" in content
    assert "(?:Content|المحتوى)" in content
    assert "(?:\\r?\\n(?:\\r?\\n)?---|\\s*$)" in content
    assert "(?:^|\\r?\\n)\\s*Filename:" in content


def test_renderer_resets_stale_conversation_after_not_found_error():
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        content = file.read()

    assert 'if (/Conversation not found/i.test(data.detail || ""))' in content
    assert "state.currentConversation = null;" in content


def test_renderer_unwraps_assistant_final_json_envelopes():
    with open("desktop/src/renderer/index.html", encoding="utf-8") as file:
        content = file.read()

    assert "function unwrapAssistantFinalEnvelope(content)" in content
    assert 'parsed.type === "assistant_final"' in content
