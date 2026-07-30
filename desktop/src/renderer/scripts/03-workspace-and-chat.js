        async function sendMessage() {
            const text = els.messageInput.value.trim();
            if (!text || state.isStreaming) {
                return;
            }
            if (state.authRequired || !state.settings.token) {
                await handleAuthFailure("لا يمكن إرسال الرسالة لأن جلسة الدسكتوب غير صالحة.");
                return;
            }

            const wsReady = await waitForWebSocketOpen();
            if (!wsReady) {
                if (state.authRequired || !state.settings.token) {
                    return;
                }
            }

            els.messageInput.value = "";
            els.messageInput.style.height = "auto";
            els.welcomeScreen.style.display = "none";
            appendMessage("user", text);
            state.currentMessages.push({ role: "user", content: text });
            const profileName = state.settings.profileName || "";

            if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
                await enqueueMessage(text, profileName);
                appendSystemMessage("تم حفظ الرسالة محلياً وسيتم إرسالها عند عودة الاتصال.");
                connectWebSocket();
                return;
            }

            showTypingIndicator();
            state.isStreaming = true;

            try {
                await sendWebSocketMessage(text, profileName);
            } catch (error) {
                resetStreamingState();
                await enqueueMessage(text, profileName);
                appendSystemMessage(`تم تحويل الرسالة إلى queue بعد فشل الإرسال: ${error.message}`);
            }
        }

        function renderProjectFiles() {
            els.selectedFilesStatus.textContent = `${state.selectedProjectFiles.size} ملف محدد كأولوية للسياق`;
            els.projectFiles.innerHTML = state.projectFiles.map((file) => `
                <div class="file-item ${state.selectedProjectFiles.has(file.path) ? "selected" : ""}" data-file-path="${file.path}">
                    <div class="d-flex justify-content-between align-items-start gap-2">
                        <div class="flex-grow-1">
                            <div class="small fw-semibold">${file.path}</div>
                            <div class="text-muted" style="font-size:11px">${(file.size / 1024).toFixed(1)} KB</div>
                        </div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-light btn-open-file" data-file-path="${file.path}" type="button">Open</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-light"} btn-select-file" data-file-path="${file.path}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? "Selected" : "Select"}
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
                    await persistSettings();
                    renderProjectFiles();
                });
            });
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
                return;
            }

            state.projectFiles = result.files || [];
            renderProjectFiles();
        }

        async function openProjectFile(filePath) {
            if (!state.projectPath) {
                return;
            }

            const targetFile = (state.projectFiles || []).find((file) => file.path === filePath);
            if (targetFile?.kind === "image" && window.electronAPI.readImageFile) {
                const imageResult = await window.electronAPI.readImageFile(state.projectPath, filePath);
                if (imageResult.error) {
                    els.writePreviewStatus.textContent = imageResult.error;
                    return;
                }

                state.currentFilePath = filePath;
                state.pendingWriteToken = null;
                els.btnApplyWrite.disabled = true;
                els.currentFilePath.textContent = filePath;
                els.fileEditor.value = `[image] ${imageResult.name} (${(imageResult.size / 1024).toFixed(1)} KB)`;
                void window.electronAPI.setDirtyState(false);
                els.writePreviewStatus.innerHTML = `<img src="${imageResult.dataUrl}" alt="${escapeHtml(imageResult.name)}" style="max-width:100%;border-radius:12px;margin-top:8px;">`;
                return;
            }

            const result = await window.electronAPI.readFile(state.projectPath, filePath);
            if (result.error) {
                els.writePreviewStatus.textContent = result.error;
                return;
            }

            state.currentFilePath = filePath;
            state.pendingWriteToken = null;
            els.btnApplyWrite.disabled = true;
            els.currentFilePath.textContent = filePath;
            els.fileEditor.value = result.content;
            void window.electronAPI.setDirtyState(false);
            els.writePreviewStatus.textContent = `تم تحميل الملف (${(result.size / 1024).toFixed(1)} KB)`;
        }

        async function prepareFileWrite() {
            if (!state.projectPath || !state.currentFilePath) {
                els.writePreviewStatus.textContent = "اختر ملفاً أولاً.";
                return;
            }

            const result = await window.electronAPI.prepareFileWrite(
                state.projectPath,
                state.currentFilePath,
                els.fileEditor.value,
            );

            if (result.error) {
                els.writePreviewStatus.textContent = result.error;
                return;
            }

            state.pendingWriteToken = result.previewToken;
            els.btnApplyWrite.disabled = false;
            els.writePreviewStatus.textContent = `Preview ready: changed ${result.summary.changedLines} line(s), ${result.summary.previousLineCount} -> ${result.summary.nextLineCount} lines.`;
        }

        async function applyPreparedWrite() {
            if (!state.pendingWriteToken) {
                return;
            }

            const result = await window.electronAPI.applyFileWrite(state.pendingWriteToken);
            if (result.error) {
                els.writePreviewStatus.textContent = result.error;
                return;
            }

            state.pendingWriteToken = null;
            void window.electronAPI.setDirtyState(false);
            els.btnApplyWrite.disabled = true;
            els.writePreviewStatus.textContent = "تم حفظ التعديل بعد الموافقة.";
            await refreshProjectFiles();
        }

        function persistCurrentProjectSelection() {
            const project = getCurrentProject();
            if (!project) {
                return;
            }
            project.selectedFiles = Array.from(state.selectedProjectFiles);
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
                    const timestamp = `<div class="timestamp">${new Date().toLocaleTimeString("ar")}</div>`;
                    state.streamingAssistantElement.innerHTML = `${renderMarkdown(lastMessage.content)}${timestamp}`;
                    scrollBottom();
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
                    break;
                case "error":
                    resetStreamingState();
                    state.pendingConversationProjectId = null;
                    appendSystemMessage(`خطأ: ${data.detail}`);
                    break;
                default:
                    break;
            }
        }

        async function sendWebSocketMessage(text, profileNameOverride = "") {
            const projectContext = await buildProjectContextForMessage(text);
            const selectedProfileName = profileNameOverride || state.settings.profileName || undefined;
            const payload = {
                type: "user_message",
                content: text,
                project_context: projectContext || undefined,
                profile_name: selectedProfileName,
                conversation_id: state.conversationResetPending ? null : (state.currentConversation || null),
                workspace: buildWorkspaceDescriptor(),
            };

            state.ws.send(JSON.stringify(payload));
        }

        async function sendMessage() {
            const text = els.messageInput.value.trim();
            if (!text || state.isStreaming) {
                return;
            }

            els.messageInput.value = "";
            els.messageInput.style.height = "auto";
            els.welcomeScreen.style.display = "none";
            appendMessage("user", text);
            state.currentMessages.push({ role: "user", content: text });
            const profileName = state.settings.profileName || "";
            state.pendingConversationProjectId = state.conversationResetPending
                ? state.currentProjectId
                : (state.currentConversation ? getConversationProjectId(state.currentConversation) : state.currentProjectId);

            if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
                await enqueueMessage(text, profileName);
                appendSystemMessage("تم حفظ الرسالة محلياً وسيتم إرسالها عند عودة الاتصال.");
                connectWebSocket();
                return;
            }

            showTypingIndicator();
            state.isStreaming = true;

            try {
                await sendWebSocketMessage(text, profileName);
            } catch (error) {
                resetStreamingState();
                state.pendingConversationProjectId = null;
                await enqueueMessage(text, profileName);
                appendSystemMessage(`تم تحويل الرسالة إلى queue بعد فشل الإرسال: ${error.message}`);
            }
        }

        function renderProjectFiles() {
            const currentProject = getCurrentProject();
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} ملف محدد للمشروع ${currentProject.name}`
                : `${state.selectedProjectFiles.size} ملف محدد كأولوية للسياق`;
            els.projectFiles.innerHTML = state.projectFiles.map((file) => `
                <div class="file-item ${state.selectedProjectFiles.has(file.path) ? "selected" : ""}" data-file-path="${file.path}">
                    <div class="d-flex justify-content-between align-items-start gap-2">
                        <div class="flex-grow-1">
                            <div class="small fw-semibold">${file.path}</div>
                            <div class="text-muted" style="font-size:11px">${(file.size / 1024).toFixed(1)} KB</div>
                        </div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-light btn-open-file" data-file-path="${file.path}" type="button">Open</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-light"} btn-select-file" data-file-path="${file.path}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? "Selected" : "Select"}
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
                return;
            }

            state.projectFiles = result.files || [];
            renderProjectFiles();
        }

        function getSpeechRecognitionCtor() {
            return window.SpeechRecognition || window.webkitSpeechRecognition || null;
        }

        const renderConversationsFixed = () => {
            const generalSessions = getGeneralSessions();
            const visibleGeneralSessions = state.settings.showAllChats
                ? generalSessions
                : generalSessions.slice(0, MAX_VISIBLE_GENERAL_SESSIONS);
            const projectsHtml = state.projects.length > 0
                ? state.projects.map((project) => {
                    const projectSessions = getProjectSessions(project.id);
                    const visibleSessions = project.showAllSessions
                        ? projectSessions
                        : projectSessions.slice(0, MAX_VISIBLE_PROJECT_SESSIONS);
                    return `
                        <div class="project-item ${state.swipedProjectId === project.id ? "swiped" : ""}" data-project-item="${project.id}">
                            <div class="project-delete-rail">
                                <button class="project-delete-btn" data-project-delete="${project.id}" type="button" title="${t("deleteProject")}">
                                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                        <path d="M9 3H15L16 5H21V7H3V5H8L9 3Z" fill="currentColor"></path>
                                        <path d="M6 8H18L17 20H7L6 8Z" fill="currentColor" opacity="0.92"></path>
                                    </svg>
                                </button>
                            </div>
                            <div class="project-card ${state.swipedProjectId === project.id ? "swiped" : ""}" data-project-swipe-surface="${project.id}">
                                <div class="project-header">
                                    <button class="project-title-btn ${state.currentProjectId === project.id ? "active" : ""}" data-project-header="${project.id}" type="button">
                                        <span class="collapse-arrow">${renderChevron(project.expanded)}</span>
                                        <div class="project-title-copy">
                                            <div class="project-name text-truncate">${escapeHtml(project.name)}</div>
                                            <span class="project-path">${escapeHtml(project.path)}</span>
                                        </div>
                                    </button>
                                    <button class="project-action-btn compact" data-project-session="${project.id}" type="button" title="${t("projectNewSession")}">
                                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
                                        </svg>
                                    </button>
                                </div>
                                ${project.expanded ? `
                                    <div class="project-sessions">
                                        ${visibleSessions.map((conversation) => renderConversationButton(conversation, "project-session-item")).join("")}
                                        ${projectSessions.length === 0 ? `<button class="empty-project-btn" data-project-session="${project.id}" type="button">${t("startFirstSession")}</button>` : ""}
                                        ${projectSessions.length > MAX_VISIBLE_PROJECT_SESSIONS ? `
                                            <button class="show-more-btn" data-project-show-more="${project.id}" type="button">
                                                ${project.showAllSessions ? t("showLess") : t("showMore")}
                                            </button>
                                        ` : ""}
                                    </div>
                                ` : ""}
                            </div>
                        </div>
                    `;
                }).join("")
                : `<button class="empty-project-btn" id="btn-add-project-empty" type="button">${t("sectionNew")}</button>`;

            els.conversationsList.innerHTML = `
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-chats-section" type="button">
                        <span style="display:inline-flex;align-items:center;gap:8px;"><span>💬</span><span>${t("chats")}</span></span>
                        <span data-sidebar-action="new-chat" style="margin-inline-start:auto;color:var(--accent);font-weight:800;padding:2px 8px;border-radius:999px;background:rgba(88,118,244,0.08);">${t("sectionNew")}</span>
                        <span class="collapse-arrow">${renderChevron(!state.settings.chatsCollapsed)}</span>
                    </button>
                </div>
                ${generalSessions.length > 0 && !state.settings.chatsCollapsed ? `
                    <div class="sidebar-group">
                        ${visibleGeneralSessions.map((conversation) => renderConversationButton(conversation)).join("")}
                        ${generalSessions.length > MAX_VISIBLE_GENERAL_SESSIONS ? `
                            <button class="show-more-btn" id="btn-toggle-all-chats" type="button">
                                ${state.settings.showAllChats ? t("showLess") : t("showMore")}
                            </button>
                        ` : ""}
                    </div>
                ` : ""}
                <div class="section-divider"></div>
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-projects-section" type="button">
                        <span style="display:inline-flex;align-items:center;gap:8px;"><span>📁</span><span>${t("projects")}</span></span>
                        <span data-sidebar-action="new-project" style="margin-inline-start:auto;color:var(--accent);font-weight:800;padding:2px 8px;border-radius:999px;background:rgba(88,118,244,0.08);">${t("sectionNew")}</span>
                        <span class="collapse-arrow">${renderChevron(!state.settings.projectsCollapsed)}</span>
                    </button>
                </div>
                ${state.settings.projectsCollapsed ? "" : `<div class="sidebar-group">${projectsHtml}</div>`}
            `;

            document.getElementById("toggle-chats-section")?.addEventListener("click", () => {
                if (event.target?.closest?.('[data-sidebar-action="new-chat"]')) {
                    newConversation();
                    return;
                }
                void toggleChatsCollapsed();
            });
            document.getElementById("toggle-projects-section")?.addEventListener("click", () => {
                if (event.target?.closest?.('[data-sidebar-action="new-project"]')) {
                    void promptAndAddProject();
                    return;
                }
                void toggleProjectsCollapsed();
            });
            document.getElementById("btn-toggle-all-chats")?.addEventListener("click", () => {
                void toggleShowAllChats();
            });
            document.getElementById("btn-add-project-empty")?.addEventListener("click", () => {
                void promptAndAddProject();
            });
            document.querySelectorAll("[data-conversation-id]").forEach((element) => {
                element.addEventListener("click", () => {
                    void loadConversation(element.dataset.conversationId);
                });
            });
            document.querySelectorAll("[data-project-header]").forEach((element) => {
                element.addEventListener("click", () => {
                    void handleProjectHeaderClick(element.dataset.projectHeader);
                });
            });
            document.querySelectorAll("[data-project-session]").forEach((element) => {
                element.addEventListener("click", () => {
                    void startProjectSession(element.dataset.projectSession);
                });
            });
            document.querySelectorAll("[data-project-delete]").forEach((element) => {
                element.addEventListener("click", () => {
                    void deleteProject(element.dataset.projectDelete);
                });
            });
            document.querySelectorAll("[data-project-show-more]").forEach((element) => {
                element.addEventListener("click", () => {
                    void toggleProjectShowMore(element.dataset.projectShowMore);
                });
            });
            document.querySelectorAll("[data-project-swipe-surface]").forEach((element) => {
                element.addEventListener("mousedown", (event) => {
                    state.projectSwipeTracker = {
                        projectId: element.dataset.projectSwipeSurface,
                        startX: event.clientX,
                    };
                });
            });
        };
        async function toggleMicrophone() {
            if (state.speechRecognitionActive && state.speechRecognition) {
                state.speechRecognition.stop();
                return;
            }

            const SpeechRecognitionCtor = getSpeechRecognitionCtor();
            if (!SpeechRecognitionCtor) {
                updateComposerStatus("التسجيل الصوتي غير مدعوم في هذا الجهاز.");
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach((track) => track.stop());
            } catch (error) {
                updateComposerStatus(`فشل الوصول إلى الميكروفون: ${error.message}`);
                return;
            }

            const recognition = new SpeechRecognitionCtor();
            recognition.lang = "ar-SA";
            recognition.interimResults = true;
            recognition.continuous = false;

            recognition.onstart = () => {
                state.speechRecognition = recognition;
                state.speechRecognitionActive = true;
                els.btnMic.classList.add("recording");
                updateComposerStatus("جاري الاستماع...");
            };
            recognition.onresult = (event) => {
                const transcript = Array.from(event.results).map((result) => result[0]?.transcript || "").join(" ").trim();
                if (transcript) {
                    els.messageInput.value = `${els.messageInput.value} ${transcript}`.trim();
                    els.messageInput.dispatchEvent(new Event("input"));
                    updateComposerStatus("تم إدراج النص الصوتي في المحادثة.");
                }
            };
            recognition.onerror = (event) => {
                updateComposerStatus(`خطأ في التسجيل الصوتي: ${event.error || "unknown"}`);
            };
            recognition.onend = () => {
                state.speechRecognitionActive = false;
                state.speechRecognition = null;
                els.btnMic.classList.remove("recording");
            };

            recognition.start();
        }

        els.messageInput.addEventListener("input", () => {
            els.messageInput.style.height = "auto";
            els.messageInput.style.height = `${Math.min(els.messageInput.scrollHeight, 120)}px`;
        });

        els.btnSend.addEventListener("click", () => {
            void sendMessage();
        });
        els.btnMic.addEventListener("click", () => {
            void toggleMicrophone();
        });
        els.composerProfileSelect.addEventListener("change", async () => {
            state.settings.profileName = els.composerProfileSelect.value.trim();
            els.settingProfile.value = state.settings.profileName;
            els.profileBadge.textContent = state.settings.profileName || state.settings.template || "default";
            await persistSettings();
        });
        els.settingProfile.addEventListener("change", () => {
            els.composerProfileSelect.value = els.settingProfile.value.trim();
        });

        els.messageInput.addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
            }
        });

        els.btnNewChat.addEventListener("click", newConversation);
        els.btnLanguageToggle.addEventListener("click", () => {
            void toggleLanguage();
        });
        els.btnSettings.addEventListener("click", () => {
            toggleSettingsPanel();
        });
        els.btnCloseSettings?.addEventListener("click", () => {
            toggleSettingsPanel(false);
        });
        els.btnCloseSettingsFooter?.addEventListener("click", () => {
            toggleSettingsPanel(false);
        });
        els.btnSaveSettings.addEventListener("click", () => {
            void saveSettings();
        });
        els.btnClearQueue.addEventListener("click", async () => {
            await setOfflineQueue([]);
        });
        els.btnPrepareWrite.addEventListener("click", () => {
            void prepareFileWrite();
        });
        els.btnApplyWrite.addEventListener("click", () => {
            void applyPreparedWrite();
        });
        els.fileEditor.addEventListener("input", () => {
            void window.electronAPI.setDirtyState(true);
        });
        els.btnCheckUpdates.addEventListener("click", () => {
            void checkForUpdates();
        });

        document.addEventListener("keydown", (event) => {
            if (event.ctrlKey && event.key === ",") {
                event.preventDefault();
                toggleSettingsPanel();
            }
            if (event.key === "Escape" && getSettingsPanelOpen()) {
                toggleSettingsPanel(false);
            }
        });
        document.addEventListener("mousedown", (event) => {
            if (!getSettingsPanelOpen()) {
                return;
            }
            if (els.settingsPanel.contains(event.target) || els.btnSettings.contains(event.target)) {
                return;
            }
            toggleSettingsPanel(false);
        });
        document.addEventListener("mouseup", handleProjectSwipeGesture);

        els.btnOpenFolder.addEventListener("click", async () => {
            await promptAndAddProject();
        });

        document.getElementById("btn-activate").addEventListener("click", async () => {
            const token = document.getElementById("act-token").value.trim();
            const password = document.getElementById("act-password").value.trim();
            const apiUrl = document.getElementById("act-api-url").value.trim();
            const statusEl = document.getElementById("act-status");

            if (!token || !password) {
                statusEl.innerHTML = "<span class=\"text-danger\">أدخل كود الدعوة وكلمة المرور</span>";
                return;
            }

            statusEl.innerHTML = "<span class=\"text-info\">جارٍ التفعيل...</span>";

            try {
                const data = await window.electronAPI.activateSession(apiUrl, token, password);

                state.settings = await window.electronAPI.setSettings({
                    ...state.settings,
                    apiUrl,
                    token: data.accessToken,
                    activationToken: "",
                    template: "default",
                });

                statusEl.innerHTML = "<span class=\"text-success\">تم التفعيل بنجاح</span>";
                setTimeout(async () => {
                    document.getElementById("activation-panel").style.display = "none";
                    await loadSettings();
                    await loadConversations();
                    connectWebSocket();
                }, 700);
            } catch (error) {
                statusEl.innerHTML = `<span class="text-danger">خطأ: ${escapeHtml(error.message)}</span>`;
            }
        });

        document.getElementById("btn-tg-gen-code").addEventListener("click", async () => {
            const codeInput = document.getElementById("tg-bind-code");
            const statusEl = document.getElementById("tg-bind-status");
            statusEl.innerHTML = "<span class=\"text-info\">جارٍ التوليد...</span>";

            try {
                const data = await apiRequest("/telegram/generate-bind-code", { method: "POST" });
                if (data.bind_code) {
                    codeInput.value = data.bind_code;
                    statusEl.innerHTML = "<span class=\"text-success\">تم توليد الكود. أرسله للبوت ثم اضغط تأكيد الربط.</span>";
                } else {
                    statusEl.innerHTML = "<span class=\"text-warning\">الحساب مربوط بالفعل.</span>";
                }
            } catch (error) {
                statusEl.innerHTML = `<span class="text-danger">خطأ: ${escapeHtml(error.message)}</span>`;
            }
        });

        document.getElementById("btn-tg-bind").addEventListener("click", async () => {
            const bindCode = document.getElementById("tg-bind-code").value.trim();
            const statusEl = document.getElementById("tg-bind-status");

            if (!bindCode) {
                statusEl.innerHTML = "<span class=\"text-danger\">ولّد الكود أولاً</span>";
                return;
            }

            statusEl.innerHTML = "<span class=\"text-info\">جارٍ التأكيد...</span>";

            try {
                await apiRequest("/telegram/bind-with-code", {
                    method: "POST",
                    body: JSON.stringify({ binding_code: bindCode }),
                });
                statusEl.innerHTML = "<span class=\"text-success\">تم الربط بنجاح.</span>";
            } catch (error) {
                statusEl.innerHTML = `<span class="text-danger">خطأ: ${escapeHtml(error.message)}</span>`;
            }
        });
