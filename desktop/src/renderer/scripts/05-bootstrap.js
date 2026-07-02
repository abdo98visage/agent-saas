        async function loadSettings() {
            state.settings = await window.electronAPI.getSettings();
            const defaultWorkspace = window.electronAPI.getDefaultWorkspaceRoot
                ? await window.electronAPI.getDefaultWorkspaceRoot()
                : null;
            state.fallbackWorkspacePath = defaultWorkspace && !defaultWorkspace.error
                ? defaultWorkspace.path || ""
                : "";
            state.authRequired = !state.settings.token;
            ensureUiSettings();
            ensureConversationTitleState();
            els.settingApiUrl.value = state.settings.apiUrl || "http://localhost:8002/api";
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
            ensureConversationTitleState();
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
                conversationTitleMap: state.settings.conversationTitleMap,
                projectOutputFilesMap: state.settings.projectOutputFilesMap,
                currentProjectId: state.currentProjectId,
                projectPath: state.projectPath,
                selectedProjectFiles: Array.from(state.selectedProjectFiles),
                settingsCategories: state.settings.settingsCategories,
            });
            state.authRequired = !state.settings.token;
            ensureConversationTitleState();
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

        async function loadConversation(id) {
            state.currentConversation = id;
            state.conversationResetPending = false;
            state.currentMessages = [];
            updateProjectSelectionFromConversation(id);
            const conversation = state.conversations.find((item) => item.conversation_id === id);
            els.chatTitle.textContent = conversation ? getConversationDisplayTitle(conversation) : (getCurrentProject()?.name || t("newChat"));
            renderConversations();
            els.welcomeScreen.style.display = "none";
            els.chatBody.innerHTML = "";
            updateComposerStatus(getCurrentProject() ? `${t("contextPrefix")} ${getCurrentProject().name}` : `${t("contextPrefix")} ${t("regularChat")} - ${t("noProject")}`);
            if (state.projectPath) {
                await refreshProjectFiles();
            }
            try {
                const data = await apiRequest(`/chat/conversations/${id}/messages`);
                state.currentMessages = data.messages || [];
                const derivedTitle = deriveTitleFromMessages(state.currentMessages);
                if (derivedTitle) {
                    rememberConversationTitle(id, derivedTitle);
                }
                state.currentMessages.forEach((message) => appendMessage(message.role, message.content));
                scrollBottom();
                renderContextSidebar();
            } catch (error) {
                console.error("Failed to load messages:", error);
            }
        }

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
            clearTransientSystemMessage();
            ensureConversationTitleState();
            const localTitle = summarizeConversationTitle(text);
            state.pendingConversationTitle = localTitle;
            els.chatTitle.textContent = localTitle;
            els.messageInput.value = "";
            els.messageInput.style.height = "auto";
            els.welcomeScreen.style.display = "none";
            appendMessage("user", text);
            state.currentMessages.push({ role: "user", content: text });
            if (state.currentConversation) {
                rememberConversationTitle(state.currentConversation, localTitle);
                await persistSettings();
            }
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

        function handleWsMessage(data) {
            switch (data.type) {
                case "start":
                    clearTransientSystemMessage();
                    startAssistantStream();
                    if (data.conversation_id && !state.currentConversation) {
                        state.currentConversation = data.conversation_id;
                        state.conversationResetPending = false;
                        markConversationProject(data.conversation_id, state.pendingConversationProjectId);
                        updateProjectSelectionFromConversation(data.conversation_id);
                        rememberConversationTitle(data.conversation_id);
                        state.pendingConversationProjectId = null;
                        void persistSettings();
                        void loadConversations();
                    }
                    break;
                case "chunk":
                case "assistant_chunk": {
                    clearTransientSystemMessage();
                    startAssistantStream();
                    const lastMessage = state.currentMessages[state.currentMessages.length - 1];
                    lastMessage.content += data.content;
                    setMessageElementContent(state.streamingAssistantElement, "assistant", lastMessage.content);
                    scrollBottom();
                    break;
                }
                case "tool_request":
                    showTransientSystemMessage(getToolRequestMessage(data.tool));
                    void executeToolRequest(data);
                    break;
                case "approval_required":
                    clearTransientSystemMessage();
                    appendSystemMessage(data.summary || data.title || "The agent requested approval for a local change.");
                    break;
                case "apply_request":
                    clearTransientSystemMessage();
                    void executeApplyRequest(data);
                    break;
                case "done":
                    clearTransientSystemMessage();
                    resetStreamingState();
                    if (data.conversation_id) {
                        if (!(state.conversationResetPending && state.pendingConversationProjectId === null)) {
                            state.currentConversation = data.conversation_id;
                            if (state.pendingConversationProjectId) {
                                markConversationProject(data.conversation_id, state.pendingConversationProjectId);
                                updateProjectSelectionFromConversation(data.conversation_id);
                            }
                        }
                        rememberConversationTitle(data.conversation_id);
                    }
                    state.pendingConversationProjectId = null;
                    state.pendingConversationTitle = "";
                    void persistSettings();
                    void loadConversations();
                    break;
                case "error":
                    clearTransientSystemMessage();
                    resetStreamingState();
                    state.pendingConversationProjectId = null;
                    appendSystemMessage(`خطأ: ${data.detail}`);
                    break;
                default:
                    break;
            }
        }

        els.messageInput.addEventListener("input", () => {
            els.messageInput.style.height = "auto";
            els.messageInput.style.height = `${Math.min(els.messageInput.scrollHeight, 248)}px`;
        });
        els.btnOpenFolderLive?.addEventListener("click", async () => {
            await promptAndAddProject();
        });
        els.composerCommandSelect?.addEventListener("change", async () => {
            state.settings.commandMode = els.composerCommandSelect.value;
            await persistSettings();
        });
        els.composerApprovalSelect?.addEventListener("change", async () => {
            state.settings.approvalMode = els.composerApprovalSelect.value;
            await persistSettings();
        });
        els.settingLanguage?.addEventListener("change", async () => {
            state.settings.locale = els.settingLanguage.value === "en" ? "en" : "ar";
            applyLocale();
            renderConversations();
            renderProjectFiles();
            await persistSettings();
        });

        (async () => {
            await loadSettings();

            if (!state.settings.token) {
                document.getElementById("activation-panel").style.display = "flex";
                return;
            }

            await loadConversations();
            connectWebSocket();
        })();
