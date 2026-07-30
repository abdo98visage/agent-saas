        function getRoleLabel(role) {
            if (role === "user") {
                return t("userRole");
            }
            if (role === "assistant") {
                return t("assistantRole");
            }
            return t("systemRole");
        }

        async function copyTextToClipboard(text) {
            try {
                await navigator.clipboard.writeText(text);
            } catch (error) {
                const textarea = document.createElement("textarea");
                textarea.value = text;
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
            }
        }

        function normalizeMessageAttachments(attachments) {
            return (Array.isArray(attachments) ? attachments : [])
                .map((item) => {
                    if (!item || typeof item !== "object") {
                        return null;
                    }
                    let sourceUrl = String(item.data_url || "");
                    if (!sourceUrl && item.signed_path) {
                        sourceUrl = new URL(String(item.signed_path), state.settings.apiUrl || "http://localhost:8001/api").toString();
                    }
                    if (!sourceUrl.startsWith("data:image/") && !sourceUrl.startsWith("https://") && !sourceUrl.startsWith("http://")) {
                        return null;
                    }
                    return { ...item, data_url: sourceUrl };
                })
                .filter(Boolean)
                .slice(0, 4)
                .map((item) => ({
                    name: String(item.name || "image").slice(0, 255),
                    mime_type: String(item.mime_type || "image/*").slice(0, 120),
                    data_url: String(item.data_url || ""),
                    size_bytes: Number(item.size_bytes || 0) || undefined,
                    source: String(item.source || "").slice(0, 100) || undefined,
                }));
        }

        function getMessageText(messageOrContent) {
            if (messageOrContent && typeof messageOrContent === "object" && !Array.isArray(messageOrContent)) {
                return String(messageOrContent.content || "");
            }
            return String(messageOrContent || "");
        }

        function getMessageAttachments(messageOrContent) {
            if (messageOrContent && typeof messageOrContent === "object" && !Array.isArray(messageOrContent)) {
                return normalizeMessageAttachments(messageOrContent.attachments);
            }
            return [];
        }

        function renderMessageAttachments(attachments) {
            const safeAttachments = normalizeMessageAttachments(attachments);
            if (!safeAttachments.length) {
                return "";
            }
            return `
                <div class="message-attachments-grid">
                    ${safeAttachments.map((attachment) => `
                        <figure class="message-attachment-card">
                            <img src="${attachment.data_url}" alt="${escapeHtml(attachment.name)}" class="message-attachment-image">
                            <figcaption class="message-attachment-caption">${escapeHtml(attachment.name)}</figcaption>
                        </figure>
                    `).join("")}
                </div>
            `;
        }

        function setMessageElementContent(element, role, messageOrContent) {
            const content = getMessageText(messageOrContent);
            const attachments = getMessageAttachments(messageOrContent);
            const body = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
            const attachmentsMarkup = renderMessageAttachments(attachments);
            const copyButton = role === "system" ? "" : `
                <button class="message-copy-btn" type="button" title="${t("copy")}">
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M9 9H19V19H9V9Z" stroke="currentColor" stroke-width="1.8"></path>
                        <path d="M5 15H4V5H14V6" stroke="currentColor" stroke-width="1.8"></path>
                    </svg>
                </button>
            `;
            element.innerHTML = `${copyButton}${attachmentsMarkup}<div class="message-body">${body}</div><div class="timestamp">${new Date().toLocaleTimeString(getLocale())}</div>`;
            const copyTrigger = element.querySelector(".message-copy-btn");
            copyTrigger?.addEventListener("click", async (event) => {
                event.stopPropagation();
                await copyTextToClipboard(content);
            });
        }

        function renderActivityFeed() {
            if (!els.activityFeed) {
                return;
            }
            const items = state.currentMessages.slice(-6).reverse();
            if (!items.length) {
                els.activityFeed.innerHTML = `<div class="activity-empty">${t("noActivity")}</div>`;
                return;
            }
            els.activityFeed.innerHTML = items.map((item) => `
                <div class="activity-item">
                    <div class="activity-role">${escapeHtml(getRoleLabel(item.role))}</div>
                    <div>${escapeHtml(String(item.content || "").slice(0, 180))}</div>
                </div>
            `).join("");
        }

        function renderContextSidebar() {
            const currentProject = getCurrentProject();
            document.getElementById("context-panel-title")?.replaceChildren(currentProject ? `${t("projectContext")} - ${currentProject.name}` : t("projectContext"));
            document.getElementById("context-panel-subtitle")?.replaceChildren(
                currentProject
                    ? (getLocale() === "en" ? "Selected project files and recent activity are shown here." : "تظهر هنا ملفات المشروع المختارة وآخر الأنشطة.")
                    : (getLocale() === "en" ? "Open a project to inspect files, or stay in chat mode and follow activity." : "افتح مشروعاً لعرض ملفاته، أو ابق في وضع المحادثة وتابع النشاط.")
            );
            els.projectPath.textContent = currentProject?.path || (getLocale() === "en" ? "No project selected" : "لا يوجد مشروع محدد");
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} ${t("filesCount")}`
                : `${t("regularChat")} - ${t("noProject")}`;
            renderActivityFeed();
        }

        function buildSettingsCategory(title, key, nodes) {
            const section = document.createElement("section");
            section.className = "settings-category";
            if (state.settings.settingsCategories?.[key]) {
                section.classList.add("collapsed");
            }
            const toggle = document.createElement("button");
            toggle.className = "settings-category-toggle";
            toggle.type = "button";
            toggle.innerHTML = `<span>${escapeHtml(title)}</span><span class="collapse-arrow">${section.classList.contains("collapsed") ? "›" : "⌄"}</span>`;
            const body = document.createElement("div");
            body.className = "settings-category-body";
            nodes.filter(Boolean).forEach((node) => body.appendChild(node));
            toggle.addEventListener("click", async () => {
                section.classList.toggle("collapsed");
                toggle.querySelector(".collapse-arrow").textContent = section.classList.contains("collapsed") ? "›" : "⌄";
                state.settings.settingsCategories[key] = section.classList.contains("collapsed");
                await persistSettings();
            });
            section.append(toggle, body);
            return section;
        }

        function buildSettingsPanelLayout() {
            if (!els.settingsPanel || els.settingsPanel.dataset.decorated === "true") {
                return;
            }
            const languageGroup = document.createElement("div");
            languageGroup.className = "mb-3";
            if (els.settingLanguage?.previousElementSibling) {
                languageGroup.appendChild(els.settingLanguage.previousElementSibling);
            }
            if (els.settingLanguage) {
                languageGroup.appendChild(els.settingLanguage);
            }
            const generalNodes = [
                els.settingApiUrl?.closest(".mb-3"),
                els.settingToken?.closest(".mb-3"),
                els.settingTemplate?.closest(".mb-3"),
                languageGroup,
                els.settingProfile?.closest(".mb-3"),
            ];
            const telegramCodeGroup = document.getElementById("tg-bind-code")?.closest(".input-group");
            const telegramNodes = [
                telegramCodeGroup?.previousElementSibling,
                telegramCodeGroup,
                document.getElementById("btn-tg-bind")?.closest(".input-group"),
                document.getElementById("tg-bind-status"),
            ];
            const workspaceNodes = [
                els.currentFilePath,
                els.fileEditor,
                els.btnPrepareWrite?.parentElement,
                els.writePreviewStatus,
            ];
            const systemNodes = [
                els.queueStatus?.previousElementSibling,
                els.queueStatus,
                els.btnClearQueue,
                els.updateStatus?.previousElementSibling,
                els.updateStatus,
                els.btnCheckUpdates,
                els.btnCloseSettingsFooter,
                els.btnSaveSettings,
            ];

            const modalHeader = document.createElement("div");
            modalHeader.className = "settings-modal-header";
            const headerText = document.createElement("div");
            headerText.innerHTML = `<h5>${getLocale() === "en" ? "Settings" : "الإعدادات"}</h5><div class="settings-inline-note">${getLocale() === "en" ? "Grouped controls with collapsible categories." : "إعدادات مرتبة ضمن أقسام قابلة للطي."}</div>`;
            modalHeader.append(headerText, els.btnCloseSettings);

            const container = document.createElement("div");
            container.append(
                buildSettingsCategory(getLocale() === "en" ? "General" : "عام", "general", generalNodes),
                buildSettingsCategory(getLocale() === "en" ? "Telegram" : "ربط التلجرام", "telegram", telegramNodes),
                buildSettingsCategory(getLocale() === "en" ? "Files and changes" : "الملفات والتعديلات", "workspace", workspaceNodes),
                buildSettingsCategory(getLocale() === "en" ? "System and execution" : "النظام والتنفيذ", "system", systemNodes),
            );

            els.settingsPanel.innerHTML = "";
            els.settingsPanel.append(modalHeader, container);
            els.settingsPanel.dataset.decorated = "true";
        }

        function getSettingsPanelOpen() {
            return els.settingsPanel.style.display !== "none";
        }

        function toggleSettingsPanel(forceState) {
            const shouldOpen = typeof forceState === "boolean" ? forceState : !getSettingsPanelOpen();
            els.settingsPanel.style.display = shouldOpen ? "block" : "none";
        }

        function applyLocale() {
            const locale = getLocale();
            document.documentElement.lang = locale;
            document.documentElement.dir = locale === "en" ? "ltr" : "rtl";
            if (els.settingLanguage) {
                els.settingLanguage.value = locale;
            }
            els.btnSend.title = t("send");
            els.btnMic.title = t("mic");
            document.getElementById("btn-send-label")?.replaceChildren(t("sendLabel"));
            els.messageInput.placeholder = t("messagePlaceholder");
            document.getElementById("welcome-screen")?.querySelector("h5")?.replaceChildren(t("welcomeTitle"));
            document.getElementById("welcome-screen")?.querySelector("p")?.replaceChildren(t("welcomeBody"));
            document.querySelector(".sidebar-header small")?.replaceChildren(locale === "en" ? "Operating system for digital employees" : "نظام التشغيل للموظفين الرقميين");
            document.getElementById("btn-open-folder-live")?.replaceChildren(locale === "en" ? "Open New Project" : "فتح مشروع جديد");
            document.getElementById("activity-title")?.replaceChildren(t("activityFeed"));
            if (!state.currentConversation) {
                els.chatTitle.textContent = t("newChat");
            }
            els.queueBadge.textContent = `${getOfflineQueue().length} ${t("queueSuffix")}`;
            renderHeaderIdentity();
            renderContextSidebar();
        }

        async function loadSettings() {
            state.settings = await window.electronAPI.getSettings();
            const defaultWorkspace = window.electronAPI.getDefaultWorkspaceRoot
                ? await window.electronAPI.getDefaultWorkspaceRoot()
                : null;
            state.fallbackWorkspacePath = defaultWorkspace && !defaultWorkspace.error
                ? defaultWorkspace.path || ""
                : "";
            ensureUiSettings();
            els.settingApiUrl.value = state.settings.apiUrl || "http://localhost:8001/api";
            els.settingToken.value = state.settings.token || "";
            els.settingTemplate.value = state.settings.template || "default";
            els.settingLanguage && (els.settingLanguage.value = state.settings.locale || "ar");
            els.composerCommandSelect && (els.composerCommandSelect.value = state.settings.commandMode || "queue");
            els.composerApprovalSelect && (els.composerApprovalSelect.value = state.settings.approvalMode || "ask_for_approval");
            state.projects = normalizeProjects(state.settings.projects);
            state.conversationProjectMap = state.settings.conversationProjectMap && typeof state.settings.conversationProjectMap === "object"
                ? state.settings.conversationProjectMap
                : {};
            state.currentProjectId = state.settings.currentProjectId || null;
            syncCurrentProjectContext();
            buildSettingsPanelLayout();
            applyLocale();
            updateComposerStatus(getCurrentProject() ? `${t("contextPrefix")} ${getCurrentProject().name}` : `${t("contextPrefix")} ${t("regularChat")} - ${t("noProject")}`);
            renderConversations();
            renderQueueStatus();
            await refreshUpdateStatus();
            await loadCurrentUser();
            await loadAssignedProfiles();
            await refreshProjectFiles();
        }

        async function saveSettings() {
            ensureUiSettings();
            state.settings.locale = els.settingLanguage?.value === "en" ? "en" : "ar";
            state.settings.commandMode = els.composerCommandSelect?.value || "queue";
            state.settings.approvalMode = els.composerApprovalSelect?.value || "ask_for_approval";
            state.settings = await window.electronAPI.setSettings({
                ...state.settings,
                apiUrl: els.settingApiUrl.value.trim(),
                token: els.settingToken.value.trim(),
                template: els.settingTemplate.value,
                profileName: els.composerProfileSelect.value.trim(),
                locale: state.settings.locale,
                commandMode: state.settings.commandMode,
                approvalMode: state.settings.approvalMode,
                projects: state.projects,
                conversationProjectMap: state.conversationProjectMap,
                currentProjectId: state.currentProjectId,
                projectPath: state.projectPath,
                selectedProjectFiles: Array.from(state.selectedProjectFiles),
                settingsCategories: state.settings.settingsCategories,
            });
            applyLocale();
            if (state.ws) {
                state.ws.close();
                state.ws = null;
            }
            if (state.settings.token) {
                connectWebSocket();
            }
            await loadCurrentUser();
            await loadConversations();
            renderAssignedProfiles();
            toggleSettingsPanel(false);
        }

        function appendMessage(role, content) {
            const div = document.createElement("div");
            div.className = `message ${role}`;
            setMessageElementContent(div, role, content);
            els.chatBody.appendChild(div);
            scrollBottom();
            renderActivityFeed();
            return div;
        }

        function renderProjectFiles() {
            const currentProject = getCurrentProject();
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} ${t("filesCount")}`
                : `${t("regularChat")} - ${t("noProject")}`;
            if (!state.projectFiles.length) {
                els.projectFiles.innerHTML = `<div class="activity-empty">${currentProject ? (getLocale() === "en" ? "No files were loaded for this project." : "لم يتم تحميل ملفات لهذا المشروع بعد.") : t("noActivity")}</div>`;
                renderContextSidebar();
                return;
            }
            els.projectFiles.innerHTML = state.projectFiles.slice().sort((a, b) => new Date(b.modifiedAt) - new Date(a.modifiedAt)).map((file) => `
                <div class="file-item ${state.selectedProjectFiles.has(file.path) ? "selected" : ""}" data-file-path="${file.path}">
                    <div class="d-flex justify-content-between align-items-start gap-2">
                        <div class="flex-grow-1">
                            <div class="small fw-semibold">${escapeHtml(file.path)}</div>
                            <div class="text-muted" style="font-size:11px">${(file.size / 1024).toFixed(1)} KB · ${new Date(file.modifiedAt).toLocaleDateString(getLocale())}</div>
                            <div class="file-badges">
                                <span class="file-badge ${file.status === "new" ? "new" : "modified"}">${file.status === "new" ? (getLocale() === "en" ? "New" : "جديد") : (getLocale() === "en" ? "Modified" : "معدل")}</span>
                                ${state.selectedProjectFiles.has(file.path) ? `<span class="file-badge selected">${getLocale() === "en" ? "Context" : "ضمن السياق"}</span>` : ""}
                            </div>
                        </div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-secondary btn-open-file" data-file-path="${file.path}" type="button">${getLocale() === "en" ? "Open" : "فتح"}</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-secondary"} btn-select-file" data-file-path="${file.path}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? (getLocale() === "en" ? "Selected" : "محدد") : (getLocale() === "en" ? "Select" : "تحديد")}
                            </button>
                        </div>
                    </div>
                    <div class="file-snippet">${escapeHtml(file.snippet || "")}</div>
                </div>
            `).join("");
            document.querySelectorAll(".btn-open-file").forEach((button) => {
                button.addEventListener("click", async () => {
                    await openProjectFile(button.dataset.filePath);
                });
            });
            document.querySelectorAll(".btn-select-file").forEach((button) => {
                button.addEventListener("click", async () => {
                    const filePath = button.dataset.filePath;
                    if (state.selectedProjectFiles.has(filePath)) {
                        state.selectedProjectFiles.delete(filePath);
                    } else {
                        state.selectedProjectFiles.add(filePath);
                    }
                    persistCurrentProjectSelection();
                    await persistSettings();
                    renderProjectFiles();
                });
            });
            renderContextSidebar();
        }

        async function refreshProjectFiles() {
            const workspacePath = getEffectiveWorkspacePath();
            if (!workspacePath) {
                state.projectFiles = [];
                renderProjectFiles();
                return;
            }
            const result = await window.electronAPI.scanFolder(workspacePath);
            if (result.error) {
                els.projectFiles.innerHTML = `<div class="text-danger">${escapeHtml(result.error)}</div>`;
                renderContextSidebar();
                return;
            }
            state.projectFiles = result.files || [];
            renderProjectFiles();
        }

        function getEffectiveWorkspacePath() {
            return state.projectPath || state.fallbackWorkspacePath || "";
        }

        function renderComposerAttachments() {
            if (!els.composerAttachments) {
                return;
            }
            const attachments = normalizeMessageAttachments(state.composerAttachments);
            if (!attachments.length) {
                els.composerAttachments.innerHTML = "";
                els.composerAttachments.style.display = "none";
                return;
            }
            els.composerAttachments.style.display = "grid";
            els.composerAttachments.innerHTML = attachments.map((attachment, index) => `
                <div class="composer-attachment-card">
                    <img src="${attachment.data_url}" alt="${escapeHtml(attachment.name)}" class="composer-attachment-image">
                    <button class="composer-attachment-remove" data-attachment-index="${index}" type="button" title="Remove image">×</button>
                    <div class="composer-attachment-name">${escapeHtml(attachment.name)}</div>
                </div>
            `).join("");
            document.querySelectorAll("[data-attachment-index]").forEach((button) => {
                button.addEventListener("click", () => {
                    const index = Number(button.dataset.attachmentIndex);
                    state.composerAttachments.splice(index, 1);
                    renderComposerAttachments();
                });
            });
        }

        async function readImageFileAsAttachment(file) {
            return await new Promise((resolve, reject) => {
                if (!file || !String(file.type || "").startsWith("image/")) {
                    reject(new Error("Only image files are supported"));
                    return;
                }
                if (Number(file.size || 0) > 6 * 1024 * 1024) {
                    reject(new Error("Image file is too large"));
                    return;
                }
                const reader = new FileReader();
                reader.onerror = () => reject(new Error("Failed to read image file"));
                reader.onload = () => resolve({
                    name: file.name || "image",
                    mime_type: file.type || "image/*",
                    data_url: String(reader.result || ""),
                    size_bytes: Number(file.size || 0) || undefined,
                    source: "chat_upload",
                });
                reader.readAsDataURL(file);
            });
        }

        async function addComposerAttachmentsFromFiles(files) {
            const imageFiles = Array.from(files || []).filter((file) => String(file.type || "").startsWith("image/")).slice(0, 4);
            if (!imageFiles.length) {
                return;
            }
            const nextAttachments = [];
            for (const file of imageFiles) {
                nextAttachments.push(await readImageFileAsAttachment(file));
            }
            state.composerAttachments = normalizeMessageAttachments([...state.composerAttachments, ...nextAttachments]).slice(0, 4);
            renderComposerAttachments();
        }

        function buildWorkspaceDescriptor() {
            const effectiveWorkspacePath = getEffectiveWorkspacePath();
            return {
                root_name: effectiveWorkspacePath ? effectiveWorkspacePath.split(/[\\/]/).pop() : "",
                root_path: effectiveWorkspacePath,
                selected_files: Array.from(state.selectedProjectFiles),
                file_paths: state.projectFiles.map((file) => file.path).slice(0, 40),
                image_paths: state.projectFiles.filter((file) => file.kind === "image").map((file) => file.path).slice(0, 100),
                command_mode: els.composerCommandSelect?.value || state.settings.commandMode || "queue",
                approval_mode: els.composerApprovalSelect?.value || state.settings.approvalMode || "ask_for_approval",
            };
        }

        async function sendWebSocketMessage(text, profileNameOverride = "", attachmentsOverride = null, queuedItem = null) {
            const sendItem = await createQueueItem(
                text,
                profileNameOverride,
                normalizeMessageAttachments(attachmentsOverride ?? state.composerAttachments),
                queuedItem,
            );
            const selectedProfileName = sendItem.profileName || state.settings.profileName || undefined;
            const payload = {
                type: "user_message",
                content: sendItem.content,
                client_message_id: sendItem.id,
                project_context: sendItem.projectContext || undefined,
                profile_name: selectedProfileName,
                attachments: normalizeMessageAttachments(sendItem.attachments),
                command_mode: sendItem.workspace?.command_mode || "queue",
                approval_mode: sendItem.workspace?.approval_mode || "ask_for_approval",
                conversation_id: sendItem.conversationId,
                workspace: sendItem.workspace,
            };
            return await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    state.pendingMessageAcks.delete(sendItem.id);
                    const error = new Error("Timed out waiting for server acknowledgement");
                    error.queueItem = sendItem;
                    reject(error);
                }, 6 * 60 * 1000);
                state.pendingMessageAcks.set(sendItem.id, {
                    resolve: (data) => {
                        clearTimeout(timeout);
                        resolve(data);
                    },
                    reject: (error) => {
                        clearTimeout(timeout);
                        error.queueItem = sendItem;
                        reject(error);
                    },
                });
                try {
                    state.ws.send(JSON.stringify(payload));
                } catch (error) {
                    state.pendingMessageAcks.delete(sendItem.id);
                    clearTimeout(timeout);
                    error.queueItem = sendItem;
                    reject(error);
                }
            });
        }

        function handleWsMessage(data) {
            switch (data.type) {
                case "start":
                    startAssistantStream();
                    if (data.conversation_id && !state.currentConversation) {
                        state.currentConversation = data.conversation_id;
                        state.conversationResetPending = false;
                        markConversationProject(data.conversation_id, state.pendingConversationProjectId);
                        updateProjectSelectionFromConversation(data.conversation_id);
                        state.pendingConversationProjectId = null;
                        void persistSettings();
                        void loadConversations();
                    }
                    break;
                case "chunk":
                case "assistant_chunk": {
                    startAssistantStream();
                    const lastMessage = state.currentMessages[state.currentMessages.length - 1];
                    lastMessage.content += data.content;
                    setMessageElementContent(state.streamingAssistantElement, "assistant", lastMessage.content);
                    scrollBottom();
                    renderActivityFeed();
                    break;
                }
                case "tool_request":
                    appendSystemMessage(`Hermes requested local tool: ${data.tool}`);
                    void executeToolRequest(data);
                    break;
                case "approval_required":
                    appendSystemMessage(data.summary || data.title || "Hermes requested approval for local changes.");
                    break;
                case "apply_request":
                    void executeApplyRequest(data);
                    break;
                case "done":
                    resetStreamingState();
                    if (data.conversation_id) {
                        if (!(state.conversationResetPending && state.pendingConversationProjectId === null)) {
                            state.currentConversation = data.conversation_id;
                            if (state.pendingConversationProjectId) {
                                markConversationProject(data.conversation_id, state.pendingConversationProjectId);
                                updateProjectSelectionFromConversation(data.conversation_id);
                            }
                        }
                    }
                    state.pendingConversationProjectId = null;
                    void persistSettings();
                    void loadConversations();
                    renderActivityFeed();
                    break;
                case "error":
                    resetStreamingState();
                    state.pendingConversationProjectId = null;
                    if (/Conversation not found/i.test(data.detail || "")) {
                        state.currentConversation = null;
                        state.conversationResetPending = false;
                        void persistSettings();
                    }
                    appendSystemMessage(`خطأ: ${data.detail}`);
                    break;
                default:
                    break;
            }
        }

        function ensureConversationTitleState() {
            if (!state.settings || typeof state.settings !== "object") {
                state.settings = {};
            }
            if (!state.settings.conversationTitleMap || typeof state.settings.conversationTitleMap !== "object") {
                state.settings.conversationTitleMap = {};
            }
            if (typeof state.pendingConversationTitle !== "string") {
                state.pendingConversationTitle = "";
            }
            if (!(state.fileTreeExpanded instanceof Set)) {
                state.fileTreeExpanded = new Set();
            }
        }

        function summarizeConversationTitle(text) {
            const normalized = String(text || "")
                .replace(/\s+/g, " ")
                .replace(/^[\s\-:;,.]+|[\s\-:;,.]+$/g, "")
                .trim();
            if (!normalized) {
                return t("newChat");
            }
            return normalized.slice(0, 60);
        }

        function isGenericConversationTitle(title) {
            const value = String(title || "").trim().toLowerCase();
            return !value
                || value === "new chat"
                || value === "chat"
                || value === "project chat"
                || value === "محادثة"
                || value === "محادثة جديدة"
                || value === "محادثة مشروع";
        }

        function deriveTitleFromMessages(messages) {
            const firstUserMessage = Array.isArray(messages)
                ? messages.find((message) => message && message.role === "user" && String(message.content || "").trim())
                : null;
            return firstUserMessage ? summarizeConversationTitle(firstUserMessage.content) : "";
        }

        function rememberConversationTitle(conversationId, fallbackText = "") {
            ensureConversationTitleState();
            if (!conversationId) {
                return;
            }
            const title = summarizeConversationTitle(fallbackText || state.pendingConversationTitle || deriveTitleFromMessages(state.currentMessages));
            if (!title || isGenericConversationTitle(title)) {
                return;
            }
            state.settings.conversationTitleMap[conversationId] = title;
            if (state.currentConversation === conversationId) {
                els.chatTitle.textContent = title;
            }
        }

        function getConversationDisplayTitle(conversation) {
            ensureConversationTitleState();
            const mapped = state.settings.conversationTitleMap?.[conversation.conversation_id];
            if (mapped) {
                return mapped;
            }
            const apiTitle = summarizeConversationTitle(conversation.title || "");
            if (apiTitle && !isGenericConversationTitle(apiTitle)) {
                return apiTitle;
            }
            return t("newChat");
        }

        function getToolRequestMessage(toolName) {
            const key = String(toolName || "").toLowerCase();
            const messages = {
                list_files: getLocale() === "en" ? "Reading project files..." : "جاري قراءة ملفات المشروع...",
                read_file: getLocale() === "en" ? "Opening the requested file..." : "جاري فتح الملف المطلوب...",
                search_files: getLocale() === "en" ? "Searching inside project files..." : "جاري البحث داخل ملفات المشروع...",
                run_command: getLocale() === "en" ? "Running a local command..." : "جاري تنفيذ أمر محلي...",
                list_directory: getLocale() === "en" ? "Reading project folders..." : "جاري قراءة مجلدات المشروع...",
            };
            return messages[key] || (getLocale() === "en" ? "Processing a local workspace action..." : "جاري تنفيذ إجراء محلي على مساحة العمل...");
        }

        function clearTransientSystemMessage() {
            if (state.transientSystemMessageElement?.parentNode) {
                state.transientSystemMessageElement.parentNode.removeChild(state.transientSystemMessageElement);
            }
            state.transientSystemMessageElement = null;
        }

        function showTransientSystemMessage(content) {
            clearTransientSystemMessage();
            const element = appendMessage("system", content);
            element.dataset.transientSystemMessage = "true";
            state.transientSystemMessageElement = element;
            return element;
        }

        function ensureContextDirectoryTree() {
            const summaryCard = document.querySelector(".context-summary-card");
            if (!summaryCard) {
                return null;
            }
            let tree = document.getElementById("context-directory-tree");
            if (!tree) {
                tree = document.createElement("div");
                tree.id = "context-directory-tree";
                tree.className = "context-tree mb-2";
                const selectedStatus = document.getElementById("context-selected-files-status");
                summaryCard.insertBefore(tree, selectedStatus || document.getElementById("context-status-live"));
            }
            return tree;
        }

        function applyStaticLayoutFixes() {
            const composerActions = document.querySelector(".composer-actions");
            if (composerActions) {
                const command = document.getElementById("composer-command-select");
                const approval = document.getElementById("composer-approval-select");
                const agent = document.getElementById("composer-profile-select");
                const mic = document.getElementById("btn-mic");
                const send = document.getElementById("btn-send");
                [command, approval, agent, mic, send].filter(Boolean).forEach((node) => composerActions.appendChild(node));
            }
            const subtitle = document.getElementById("context-panel-subtitle");
            if (subtitle && !subtitle.dataset.fixed) {
                subtitle.textContent = "/";
                subtitle.dataset.fixed = "true";
            }
            ensureContextDirectoryTree();
            if (els.btnOpenFolderLive) {
                els.btnOpenFolderLive.style.display = "none";
            }
            if (els.projectPath) {
                els.projectPath.style.display = "none";
            }
            document.getElementById("activity-title")?.closest(".context-section-card")?.remove();
        }

        function buildDirectorySummaryMarkup() {
            const tree = ensureContextDirectoryTree();
            if (!tree) {
                return;
            }
            if (!state.projectPath) {
                tree.innerHTML = "";
                return;
            }
            const outputFiles = state.projectFiles
                .filter((file) => file.status === "new" || file.status === "modified")
                .sort((a, b) => new Date(b.modifiedAt) - new Date(a.modifiedAt))
                .slice(0, 10);
            if (!outputFiles.length) {
                tree.innerHTML = `<div class="context-tree-folder"><div class="context-tree-folder-files">${getLocale() === "en" ? "No created or modified files yet." : "لا توجد ملفات جديدة أو معدلة بعد."}</div></div>`;
                return;
            }
            const markup = outputFiles
                .map((file) => `
                    <div class="context-tree-folder">
                        <div class="context-tree-folder-name">${escapeHtml(file.path.split(/[\\/]+/).pop() || file.path)}</div>
                        <div class="context-tree-folder-files">
                            ${escapeHtml(file.path)} · ${(file.size / 1024).toFixed(1)} KB · ${new Date(file.modifiedAt).toLocaleDateString(getLocale())} · ${file.status === "new" ? (getLocale() === "en" ? "New" : "جديد") : (getLocale() === "en" ? "Modified" : "معدل")}
                        </div>
                    </div>
                `)
                .join("");
            tree.innerHTML = markup;
        }

        async function persistSettings() {
            ensureUiSettings();
            ensureConversationTitleState();
            const payload = {
                ...state.settings,
                projects: state.projects,
                conversationProjectMap: state.conversationProjectMap,
                conversationTitleMap: state.settings.conversationTitleMap,
                projectOutputFilesMap: state.settings.projectOutputFilesMap,
                currentProjectId: state.currentProjectId,
                projectPath: state.projectPath,
                selectedProjectFiles: Array.from(state.selectedProjectFiles),
            };
            state.settings = await window.electronAPI.setSettings(payload);
            ensureConversationTitleState();
            renderQueueStatus();
        }

        function renderConversationButton(conversation, className = "general-session-item") {
            const activeClass = state.currentConversation === conversation.conversation_id ? "active" : "";
            return `
                <button class="${className} ${activeClass}" data-conversation-id="${conversation.conversation_id}" type="button">
                    <div class="text-truncate">${escapeHtml(getConversationDisplayTitle(conversation))}</div>
                    <span class="project-session-meta">${new Date(conversation.created_at).toLocaleDateString(getLocale())}</span>
                </button>
            `;
        }

        const originalNewConversation = typeof newConversation === "function" ? newConversation : null;
        if (originalNewConversation) {
            newConversation = function overrideNewConversation() {
                state.composerAttachments = [];
                renderComposerAttachments();
                return originalNewConversation();
            };
        }

        function renderContextSidebar() {
            applyStaticLayoutFixes();
            const currentProject = getCurrentProject();
            document.getElementById("context-panel-title")?.replaceChildren(t("projectContext"));
            document.getElementById("context-panel-subtitle")?.replaceChildren(currentProject?.path || "/");
            els.projectPath.textContent = currentProject?.path || (getLocale() === "en" ? "No project selected" : "لا يوجد مشروع محدد");
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} ${t("filesCount")}`
                : `${t("regularChat")} - ${t("noProject")}`;
            buildDirectorySummaryMarkup();
        }

        function renderProjectFiles() {
            const currentProject = getCurrentProject();
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} ${t("filesCount")}`
                : `${t("regularChat")} - ${t("noProject")}`;
            if (!state.projectFiles.length) {
                els.projectFiles.innerHTML = `<div class="activity-empty">${currentProject ? (getLocale() === "en" ? "No files were loaded for this project." : "لم يتم تحميل ملفات لهذا المشروع بعد.") : t("noActivity")}</div>`;
                renderContextSidebar();
                return;
            }
            const buildTree = () => {
                const root = { folders: new Map(), files: [] };
                state.projectFiles.forEach((file) => {
                    const parts = String(file.path || "").split(/[\\/]+/).filter(Boolean);
                    let cursor = root;
                    for (let index = 0; index < parts.length; index += 1) {
                        const part = parts[index];
                        const isFile = index === parts.length - 1;
                        if (isFile) {
                            cursor.files.push(file);
                            return;
                        }
                        if (!cursor.folders.has(part)) {
                            cursor.folders.set(part, { folders: new Map(), files: [], fullPath: parts.slice(0, index + 1).join("/") });
                        }
                        cursor = cursor.folders.get(part);
                    }
                });
                return root;
            };
            const renderFileCard = (file) => `
                <div class="file-item ${state.selectedProjectFiles.has(file.path) ? "selected" : ""}" data-file-path="${escapeHtml(file.path)}">
                    <div class="file-name">${escapeHtml(file.path.split(/[\\/]+/).pop() || file.path)}</div>
                    <div class="file-meta-row">
                        <div class="file-meta-group">
                            <span class="file-meta-text">${(file.size / 1024).toFixed(1)} KB · ${new Date(file.modifiedAt).toLocaleDateString(getLocale())}</span>
                            <div class="file-badges">
                                <span class="file-badge ${file.status === "new" ? "new" : "modified"}">${file.status === "new" ? (getLocale() === "en" ? "New" : "جديد") : (getLocale() === "en" ? "Modified" : "معدل")}</span>
                                ${state.selectedProjectFiles.has(file.path) ? `<span class="file-badge selected">${getLocale() === "en" ? "Context" : "ضمن السياق"}</span>` : ""}
                            </div>
                        </div>
                        <div class="file-action-group">
                            <button class="btn btn-sm btn-outline-secondary btn-open-file" data-file-path="${escapeHtml(file.path)}" type="button">${getLocale() === "en" ? "Open" : "فتح"}</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-secondary"} btn-select-file" data-file-path="${escapeHtml(file.path)}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? (getLocale() === "en" ? "Selected" : "محدد") : (getLocale() === "en" ? "Select" : "تحديد")}
                            </button>
                        </div>
                    </div>
                </div>
            `;
            const renderTreeNode = (node, currentPath = "") => {
                const folders = Array.from(node.folders.entries()).sort((a, b) => a[0].localeCompare(b[0]));
                const files = node.files.slice().sort((a, b) => a.path.localeCompare(b.path));
                return `
                    ${folders.map(([folderName, folderNode]) => {
                        const folderPath = currentPath ? `${currentPath}/${folderName}` : folderName;
                        const isExpanded = state.fileTreeExpanded.has(folderPath);
                        return `
                            <div class="project-tree-node">
                                <button class="project-tree-folder-toggle" data-folder-toggle="${escapeHtml(folderPath)}" type="button">
                                    <span class="project-tree-chevron">${isExpanded ? "▾" : "▸"}</span>
                                    <span>${escapeHtml(folderName)}</span>
                                </button>
                                ${isExpanded ? `<div class="project-tree-children">${renderTreeNode(folderNode, folderPath)}</div>` : ""}
                            </div>
                        `;
                    }).join("")}
                    ${files.map((file) => renderFileCard(file)).join("")}
                `;
            };
            const projectLabel = escapeHtml(currentProject?.name || state.projectPath.split(/[\\/]+/).pop() || "Project");
            const tree = buildTree();
            els.projectFiles.innerHTML = `
                <div class="project-file-tree">
                    <div class="project-tree-root">
                        <div class="project-tree-root-label">
                            <span class="project-tree-chevron">▾</span>
                            <span>${projectLabel}</span>
                        </div>
                        <div class="project-tree-children">${renderTreeNode(tree)}</div>
                    </div>
                </div>
            `;
            document.querySelectorAll("[data-folder-toggle]").forEach((button) => {
                button.addEventListener("click", () => {
                    const folderPath = button.dataset.folderToggle;
                    if (state.fileTreeExpanded.has(folderPath)) {
                        state.fileTreeExpanded.delete(folderPath);
                    } else {
                        state.fileTreeExpanded.add(folderPath);
                    }
                    renderProjectFiles();
                });
            });
            document.querySelectorAll(".btn-open-file").forEach((button) => {
                button.addEventListener("click", async () => {
                    await openProjectFile(button.dataset.filePath);
                });
            });
            document.querySelectorAll(".btn-select-file").forEach((button) => {
                button.addEventListener("click", async () => {
                    const filePath = button.dataset.filePath;
                    if (state.selectedProjectFiles.has(filePath)) {
                        state.selectedProjectFiles.delete(filePath);
                    } else {
                        state.selectedProjectFiles.add(filePath);
                    }
                    persistCurrentProjectSelection();
                    await persistSettings();
                    renderProjectFiles();
                });
            });
            renderContextSidebar();
        }

        function applyLocale() {
            applyStaticLayoutFixes();
            const locale = getLocale();
            document.documentElement.lang = locale;
            document.documentElement.dir = locale === "en" ? "ltr" : "rtl";
            if (els.settingLanguage) {
                els.settingLanguage.value = locale;
            }
            els.btnSend.title = t("send");
            els.btnMic.title = t("mic");
            document.getElementById("btn-send-label")?.replaceChildren(t("sendLabel"));
            els.messageInput.placeholder = t("messagePlaceholder");
            document.getElementById("welcome-screen")?.querySelector("h5")?.replaceChildren(t("welcomeTitle"));
            document.getElementById("welcome-screen")?.querySelector("p")?.replaceChildren(t("welcomeBody"));
            document.querySelector(".sidebar-header small")?.replaceChildren(locale === "en" ? "Operating system for digital employees" : "نظام التشغيل للموظفين الرقميين");
            if (!state.currentConversation) {
                els.chatTitle.textContent = t("newChat");
            }
            els.queueBadge.textContent = `${getOfflineQueue().length} ${t("queueSuffix")}`;
            renderHeaderIdentity();
            renderContextSidebar();
        }
