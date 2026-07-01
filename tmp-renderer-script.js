
        const MAX_VISIBLE_PROJECT_SESSIONS = 5;
        const MAX_VISIBLE_GENERAL_SESSIONS = 6;

        const state = {
            settings: {},
            conversations: [],
            currentConversation: null,
            currentMessages: [],
            currentUser: null,
            assignedProfiles: [],
            projects: [],
            conversationProjectMap: {},
            currentProjectId: null,
            pendingConversationProjectId: null,
            conversationResetPending: false,
            projectPath: null,
            projectFiles: [],
            selectedProjectFiles: new Set(),
            currentFilePath: null,
            pendingWriteToken: null,
            isStreaming: false,
            ws: null,
            heartbeatInterval: null,
            authRequired: false,
            typingElement: null,
            streamingAssistantElement: null,
            speechRecognition: null,
            speechRecognitionActive: false,
            swipedProjectId: null,
            projectSwipeTracker: null,
            savedArtifactKeys: new Set(),
        };

        const els = {
            chatBody: document.getElementById("chat-body"),
            messageInput: document.getElementById("message-input"),
            btnSend: document.getElementById("btn-send"),
            btnMic: document.getElementById("btn-mic"),
            btnNewChat: document.getElementById("btn-new-chat"),
            btnLanguageToggle: document.getElementById("btn-language-toggle"),
            btnSettings: document.getElementById("btn-settings"),
            composerCommandSelect: document.getElementById("composer-command-select"),
            composerApprovalSelect: document.getElementById("composer-approval-select"),
            composerProfileSelect: document.getElementById("composer-profile-select"),
            composerStatus: document.getElementById("composer-status"),
            conversationsList: document.getElementById("conversations-list"),
            chatTitle: document.getElementById("chat-title"),
            profileBadge: document.getElementById("profile-badge"),
            queueBadge: document.getElementById("queue-badge"),
            employeeName: document.getElementById("employee-name"),
            employeeMeta: document.getElementById("employee-meta"),
            welcomeScreen: document.getElementById("welcome-screen"),
            settingsPanel: document.getElementById("settings-panel"),
            contextPanel: document.getElementById("context-panel"),
            btnCloseSettings: document.getElementById("btn-close-settings"),
            btnCloseSettingsFooter: document.getElementById("btn-close-settings-footer"),
            settingApiUrl: document.getElementById("setting-api-url"),
            settingToken: document.getElementById("setting-token"),
            settingTemplate: document.getElementById("setting-template"),
            settingLanguage: document.getElementById("setting-language"),
            settingProfile: document.getElementById("setting-profile"),
            settingProfileStatus: document.getElementById("setting-profile-status"),
            btnOpenFolder: document.getElementById("btn-open-folder"),
            btnOpenFolderLive: document.getElementById("btn-open-folder-live"),
            btnSaveSettings: document.getElementById("btn-save-settings"),
            projectPath: document.getElementById("context-project-path"),
            projectFiles: document.getElementById("context-project-files"),
            contextStatus: document.getElementById("context-status-live"),
            selectedFilesStatus: document.getElementById("context-selected-files-status"),
            activityFeed: document.getElementById("activity-feed"),
            queueStatus: document.getElementById("queue-status"),
            btnClearQueue: document.getElementById("btn-clear-queue"),
            updateStatus: document.getElementById("update-status"),
            btnCheckUpdates: document.getElementById("btn-check-updates"),
            currentFilePath: document.getElementById("current-file-path"),
            fileEditor: document.getElementById("file-editor"),
            btnPrepareWrite: document.getElementById("btn-prepare-write"),
            btnApplyWrite: document.getElementById("btn-apply-write"),
            writePreviewStatus: document.getElementById("write-preview-status"),
        };

        function getOfflineQueue() {
            return Array.isArray(state.settings.offlineQueue) ? state.settings.offlineQueue : [];
        }

        function ensureUiSettings() {
            state.settings.chatsCollapsed = Boolean(state.settings.chatsCollapsed);
            state.settings.projectsCollapsed = Boolean(state.settings.projectsCollapsed);
            state.settings.showAllChats = Boolean(state.settings.showAllChats);
            state.settings.locale = state.settings.locale === "en" ? "en" : "ar";
            state.settings.commandMode = state.settings.commandMode || "queue";
            state.settings.approvalMode = state.settings.approvalMode || "ask_for_approval";
            state.settings.settingsCategories = state.settings.settingsCategories && typeof state.settings.settingsCategories === "object"
                ? state.settings.settingsCategories
                : {};
        }

        const translations = {
            ar: {
                newChat: "محادثة جديدة",
                sectionNew: "+ جديد",
                chats: "المحادثات",
                projects: "المشاريع",
                addProject: "مشروع جديد",
                openDirectory: "فتح مشروع جديد",
                showMore: "إظهار المزيد",
                showLess: "إظهار أقل",
                hideSessions: "إخفاء الجلسات",
                showSessions: "إظهار الجلسات",
                deleteProject: "حذف المشروع من القائمة",
                projectNewSession: "محادثة جديدة داخل المشروع",
                startFirstSession: "ابدأ أول جلسة داخل المشروع",
                settings: "الإعدادات",
                language: "EN",
                welcomeTitle: "مرحباً بك في KarzounOS",
                welcomeBody: "ابدأ محادثة جديدة أو اختر محادثة سابقة.",
                messagePlaceholder: "اكتب رسالتك هنا...",
                send: "إرسال",
                mic: "تسجيل صوتي",
                contextPrefix: "السياق الحالي:",
                projectContext: "سياق المشروع",
                activityFeed: "نشاط المحادثة",
                noActivity: "لا يوجد نشاط حديث بعد.",
                filesCount: "ملفات مختارة للسياق",
                regularChat: "محادثة عادية",
                noProject: "بدون مشروع",
                queueSuffix: "قيد الانتظار",
                sendLabel: "إرسال",
                userRole: "أنت",
                assistantRole: "الوكيل",
                systemRole: "النظام",
                copy: "نسخ",
            },
            en: {
                newChat: "New Chat",
                sectionNew: "+ New",
                chats: "Chats",
                projects: "Projects",
                addProject: "New Project",
                openDirectory: "Open New Project",
                showMore: "Show more...",
                showLess: "Show less",
                hideSessions: "Hide sessions",
                showSessions: "Show sessions",
                deleteProject: "Remove project",
                projectNewSession: "New project chat",
                startFirstSession: "Start the first session in this project",
                settings: "Settings",
                language: "AR",
                welcomeTitle: "Welcome to KarzounOS",
                welcomeBody: "Start a new chat or choose a previous conversation.",
                messagePlaceholder: "Type your message here...",
                send: "Send",
                mic: "Voice input",
                contextPrefix: "Current context:",
                projectContext: "Project context",
                activityFeed: "Conversation activity",
                noActivity: "No recent activity yet.",
                filesCount: "files selected for context",
                regularChat: "Regular chat",
                noProject: "No project",
                queueSuffix: "queued",
                sendLabel: "Send",
                userRole: "You",
                assistantRole: "Agent",
                systemRole: "System",
                copy: "Copy",
            },
        };

        function getLocale() {
            return state.settings.locale === "en" ? "en" : "ar";
        }

        function t(key) {
            const locale = getLocale();
            return translations[locale][key] || translations.ar[key] || key;
        }

        function applyLocale() {
            const locale = getLocale();
            document.documentElement.lang = locale;
            document.documentElement.dir = locale === "en" ? "ltr" : "rtl";
            els.btnLanguageToggle.textContent = t("language");
            els.btnLanguageToggle.title = locale === "en" ? "Switch to Arabic" : "التبديل إلى الإنجليزية";
            els.btnSettings.title = t("settings");
            els.btnSend.title = t("send");
            els.btnMic.title = t("mic");
            els.messageInput.placeholder = t("messagePlaceholder");
            document.getElementById("welcome-screen")?.querySelector("h5")?.replaceChildren(t("welcomeTitle"));
            document.getElementById("welcome-screen")?.querySelector("p")?.replaceChildren(t("welcomeBody"));
            document.querySelector(".sidebar-header small")?.replaceChildren(locale === "en" ? "Operating system for digital employees" : "نظام التشغيل للموظفين الرقميين");
            document.getElementById("btn-save-settings")?.replaceChildren(locale === "en" ? "Save Settings" : "حفظ الإعدادات");
            document.getElementById("btn-close-settings-footer")?.replaceChildren(locale === "en" ? "Close" : "إغلاق");
            document.getElementById("btn-open-folder")?.replaceChildren(locale === "en" ? "Open directory" : "اختيار مجلد");
            document.getElementById("btn-check-updates")?.replaceChildren(locale === "en" ? "Check updates" : "فحص التحديثات");
            document.getElementById("btn-clear-queue")?.replaceChildren(locale === "en" ? "Clear queued messages" : "مسح الرسائل المعلقة");
            document.getElementById("btn-tg-gen-code")?.replaceChildren(locale === "en" ? "Generate code" : "توليد كود");
            document.getElementById("btn-tg-bind")?.replaceChildren(locale === "en" ? "Confirm link" : "تأكيد الربط");
            if (!state.currentConversation) {
                els.chatTitle.textContent = t("newChat");
            }
            els.queueBadge.textContent = `${getOfflineQueue().length} ${t("queueSuffix")}`;
            renderHeaderIdentity();
        }

        function escapeJsString(text) {
            return String(text || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
        }

        function normalizeProjects(projects) {
            return (Array.isArray(projects) ? projects : []).map((project) => ({
                id: project.id || `project-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                name: project.name || (project.path ? project.path.split(/[\\/]/).pop() : "Project"),
                path: project.path || "",
                selectedFiles: Array.isArray(project.selectedFiles) ? project.selectedFiles : [],
                createdAt: project.createdAt || new Date().toISOString(),
                lastOpenedAt: project.lastOpenedAt || project.createdAt || new Date().toISOString(),
                expanded: project.expanded !== false,
                showAllSessions: Boolean(project.showAllSessions),
            })).filter((project) => project.path);
        }

        function getCurrentProject() {
            return state.projects.find((project) => project.id === state.currentProjectId) || null;
        }

        function getConversationProjectId(conversationId) {
            return state.conversationProjectMap[conversationId] || null;
        }

        function getProjectSessions(projectId) {
            return state.conversations
                .filter((conversation) => getConversationProjectId(conversation.conversation_id) === projectId)
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        }

        function getGeneralSessions() {
            return state.conversations
                .filter((conversation) => !getConversationProjectId(conversation.conversation_id))
                .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        }

        function syncCurrentProjectContext() {
            const project = getCurrentProject();
            state.projectPath = project ? project.path : null;
            state.selectedProjectFiles = new Set(project?.selectedFiles || []);
            els.projectPath.textContent = state.projectPath || "";
        }

        function updateComposerStatus(message = "") {
            els.composerStatus.textContent = message;
        }

        function renderHeaderIdentity() {
            const locale = getLocale();
            const selectedProfile = state.settings.profileName || state.settings.template || "default";
            const fallbackName = locale === "en" ? "Unknown employee" : "موظف غير معروف";
            const fallbackMeta = locale === "en" ? "Open the desktop with an employee account" : "افتح الدسكتوب بحساب موظف";
            const employeeName = String(state.currentUser?.full_name || "").trim()
                || String(state.currentUser?.email || "").trim().split("@")[0]
                || fallbackName;
            const metaParts = [];

            if (state.currentUser?.email) {
                metaParts.push(state.currentUser.email);
            }
            metaParts.push(`Hermes: ${selectedProfile}`);

            if (els.employeeName) {
                els.employeeName.textContent = employeeName;
            }
            if (els.employeeMeta) {
                els.employeeMeta.textContent = metaParts.join(" â€¢ ") || fallbackMeta;
            }
            if (els.profileBadge) {
                els.profileBadge.textContent = selectedProfile;
            }
        }

        function markConversationProject(conversationId, projectId) {
            if (!conversationId) {
                return;
            }

            if (projectId) {
                state.conversationProjectMap[conversationId] = projectId;
            } else {
                delete state.conversationProjectMap[conversationId];
            }
        }

        function updateProjectSelectionFromConversation(conversationId) {
            const projectId = conversationId ? getConversationProjectId(conversationId) : null;
            state.currentProjectId = projectId;
            syncCurrentProjectContext();
        }

        async function saveProjectState() {
            await persistSettings();
            renderConversations();
        }

        function renderAssignedProfiles() {
            const selectedProfileName = state.settings.profileName || "";
            const optionsHtml = [`<option value="">${getLocale() === "en" ? "Default assigned profile" : "Ø§Ù„Ù…Ù„Ù Ø§Ù„Ø§ÙØªØ±Ø§Ø¶ÙŠ Ø§Ù„Ù…Ø®ØµØµ"}</option>`]
                .concat(state.assignedProfiles.map((profile) => `
                    <option value="${escapeHtml(profile.name)}" ${selectedProfileName === profile.name ? "selected" : ""}>
                        ${escapeHtml(profile.name)}
                    </option>
                `))
                .join("");
            els.settingProfile.innerHTML = optionsHtml;
            els.composerProfileSelect.innerHTML = optionsHtml;
            els.composerProfileSelect.value = selectedProfileName;

            if (!state.settings.token) {
                els.settingProfileStatus.textContent = "Login or activate the app to load assigned profiles.";
                renderHeaderIdentity();
                return;
            }
            if (state.assignedProfiles.length === 0) {
                els.settingProfileStatus.textContent = "No assigned profiles were returned by the platform.";
                renderHeaderIdentity();
                return;
            }
            els.settingProfileStatus.textContent = `${state.assignedProfiles.length} assigned profile(s) available.`;
            renderHeaderIdentity();
        }

        async function loadCurrentUser() {
            if (!state.settings.token) {
                state.currentUser = null;
                renderHeaderIdentity();
                return;
            }

            try {
                state.currentUser = await apiRequest("/auth/me");
            } catch (error) {
                console.error("Failed to load current user:", error);
                state.currentUser = null;
            }

            renderHeaderIdentity();
        }

        async function loadAssignedProfiles() {
            if (!state.settings.token) {
                state.assignedProfiles = [];
                renderAssignedProfiles();
                return;
            }

            try {
                const data = await apiRequest("/auth/assigned-profiles");
                state.assignedProfiles = data.profiles || [];
                if (
                    state.assignedProfiles.length > 0
                    && (!state.settings.profileName || !state.assignedProfiles.some((profile) => profile.name === state.settings.profileName))
                ) {
                    state.settings.profileName = state.assignedProfiles[0].name;
                    await persistSettings();
                }
            } catch (error) {
                state.assignedProfiles = [];
                els.settingProfileStatus.textContent = `Failed to load assigned profiles: ${error.message}`;
            }

            renderAssignedProfiles();
        }

        async function persistSettings() {
            ensureUiSettings();
            const payload = {
                ...state.settings,
                projects: state.projects,
                conversationProjectMap: state.conversationProjectMap,
                currentProjectId: state.currentProjectId,
                projectPath: state.projectPath,
                selectedProjectFiles: Array.from(state.selectedProjectFiles),
            };
            state.settings = await window.electronAPI.setSettings(payload);
            renderQueueStatus();
        }

        async function apiRequest(path, options = {}) {
            const token = state.settings.token;
            const headers = { "Content-Type": "application/json", ...options.headers };
            if (token) {
                headers.Authorization = `Bearer ${token}`;
            }

            const response = await fetch(`${state.settings.apiUrl}${path}`, {
                ...options,
                headers,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.detail || `API error: ${response.status}`);
            }
            return data;
        }

        function escapeHtml(text) {
            const div = document.createElement("div");
            div.textContent = text;
            return div.innerHTML;
        }

        function renderMarkdown(text) {
            let html = escapeHtml(text);
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, "<pre><code>$2</code></pre>");
            html = html.replace(/`([^`]+)`/g, "<code class=\"bg-dark px-1 rounded\">$1</code>");
            html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
            html = html.replace(/\n/g, "<br>");
            return html;
        }

        function scrollBottom() {
            els.chatBody.scrollTop = els.chatBody.scrollHeight;
        }

        function appendMessage(role, content) {
            const div = document.createElement("div");
            div.className = `message ${role}`;
            const body = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
            div.innerHTML = `${body}<div class="timestamp">${new Date().toLocaleTimeString("ar")}</div>`;
            els.chatBody.appendChild(div);
            scrollBottom();
            return div;
        }

        function appendSystemMessage(content) {
            return appendMessage("system", content);
        }

        function showTypingIndicator() {
            removeTypingIndicator();
            const div = document.createElement("div");
            div.className = "message assistant";
            div.innerHTML = "<div class=\"typing-indicator\"><span></span><span></span><span></span></div>";
            els.chatBody.appendChild(div);
            state.typingElement = div;
            scrollBottom();
        }

        function removeTypingIndicator() {
            if (state.typingElement && state.typingElement.parentNode) {
                state.typingElement.parentNode.removeChild(state.typingElement);
            }
            state.typingElement = null;
        }

        function startAssistantStream() {
            removeTypingIndicator();
            if (!state.streamingAssistantElement) {
                state.currentMessages.push({ role: "assistant", content: "" });
                state.streamingAssistantElement = appendMessage("assistant", "");
            }
        }

        function resetStreamingState() {
            state.isStreaming = false;
            state.streamingAssistantElement = null;
            removeTypingIndicator();
        }

        async function handleAuthFailure(message = "") {
            state.authRequired = true;
            state.currentUser = null;
            resetStreamingState();
            if (state.heartbeatInterval) {
                clearInterval(state.heartbeatInterval);
                state.heartbeatInterval = null;
            }
            if (state.ws) {
                try {
                    state.ws.onclose = null;
                    state.ws.close();
                } catch {}
                state.ws = null;
            }
            state.settings.token = "";
            els.settingToken.value = "";
            document.getElementById("activation-panel").style.display = "flex";
            document.getElementById("act-status").innerHTML = `<span class="text-danger">${escapeHtml(message || "Ø§Ù†ØªÙ‡Øª Ø§Ù„Ø¬Ù„Ø³Ø© Ø§Ù„Ø­Ø§Ù„ÙŠØ©. ÙØ¹Ù‘Ù„ Ø§Ù„Ø­Ø³Ø§Ø¨ Ø£Ùˆ Ø³Ø¬Ù‘Ù„ Ø§Ù„Ø¯Ø®ÙˆÙ„ Ù…Ù† Ø¬Ø¯ÙŠØ¯.")}</span>`;
            await window.electronAPI.setSettings({
                ...state.settings,
                token: "",
            });
            renderHeaderIdentity();
        }

        function renderQueueStatus() {
            const queue = getOfflineQueue();
            els.queueBadge.textContent = `${queue.length} ${t("queueSuffix")}`;
            els.queueStatus.textContent = queue.length > 0
                ? `ÙŠÙˆØ¬Ø¯ ${queue.length} Ø±Ø³Ø§Ù„Ø© Ø¨Ø§Ù†ØªØ¸Ø§Ø± Ø¹ÙˆØ¯Ø© Ø§Ù„Ø§ØªØµØ§Ù„.`
                : "Ù„Ø§ ØªÙˆØ¬Ø¯ Ø±Ø³Ø§Ø¦Ù„ Ù…Ø¹Ù„Ù‚Ø©.";
        }

        async function setOfflineQueue(queue) {
            state.settings.offlineQueue = queue;
            await persistSettings();
        }

        async function enqueueMessage(content, profileName = "") {
            const queue = getOfflineQueue();
            queue.push({
                id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
                content,
                profileName,
                createdAt: new Date().toISOString(),
            });
            await setOfflineQueue(queue);
        }

        async function flushQueuedMessages() {
            const queue = [...getOfflineQueue()];
            if (!state.ws || state.ws.readyState !== WebSocket.OPEN || queue.length === 0) {
                return;
            }

            const remaining = [];
            for (const item of queue) {
                try {
                    await sendWebSocketMessage(item.content, item.profileName || "");
                } catch (error) {
                    remaining.push(item);
                    appendSystemMessage(`ØªØ¹Ø°Ø± Ø¥Ø±Ø³Ø§Ù„ Ø±Ø³Ø§Ù„Ø© Ù…Ø¹Ù„Ù‚Ø©: ${error.message}`);
                }
            }
            await setOfflineQueue(remaining);
        }

        function renderUpdateStatus(status) {
            if (!status) {
                els.updateStatus.textContent = "Update status unavailable.";
                return;
            }
            const checked = status.lastCheckedAt ? ` - last checked: ${new Date(status.lastCheckedAt).toLocaleString()}` : "";
            els.updateStatus.textContent = `${status.message || status.state || "unknown"}${checked}`;
        }

        async function refreshUpdateStatus() {
            if (!window.electronAPI.getUpdateStatus) {
                renderUpdateStatus(null);
                return;
            }
            renderUpdateStatus(await window.electronAPI.getUpdateStatus());
        }

        async function checkForUpdates() {
            if (!window.electronAPI.checkForUpdates) {
                renderUpdateStatus(null);
                return;
            }
            renderUpdateStatus(await window.electronAPI.checkForUpdates());
        }

        async function loadSettings() {
            state.settings = await window.electronAPI.getSettings();
            ensureUiSettings();
            els.settingApiUrl.value = state.settings.apiUrl || "http://localhost:8002/api";
            els.settingToken.value = state.settings.token || "";
            els.settingTemplate.value = state.settings.template || "default";
            state.projects = normalizeProjects(state.settings.projects);
            state.conversationProjectMap = state.settings.conversationProjectMap && typeof state.settings.conversationProjectMap === "object"
                ? state.settings.conversationProjectMap
                : {};
            state.currentProjectId = state.settings.currentProjectId || null;
            syncCurrentProjectContext();
            els.profileBadge.textContent = state.settings.profileName || state.settings.template || "default";
            applyLocale();
            updateComposerStatus(getCurrentProject() ? `${t("contextPrefix")} ${getCurrentProject().name}` : `${t("contextPrefix")} ${t("regularChat")} - ${t("noProject")}`);
            renderQueueStatus();
            await refreshUpdateStatus();
            await loadCurrentUser();
            await loadAssignedProfiles();

            await refreshProjectFiles();
        }

        async function saveSettings() {
            ensureUiSettings();
            state.settings = await window.electronAPI.setSettings({
                ...state.settings,
                apiUrl: els.settingApiUrl.value.trim(),
                token: els.settingToken.value.trim(),
                template: els.settingTemplate.value,
                profileName: els.composerProfileSelect.value.trim(),
                projects: state.projects,
                conversationProjectMap: state.conversationProjectMap,
                currentProjectId: state.currentProjectId,
                projectPath: state.projectPath,
                selectedProjectFiles: Array.from(state.selectedProjectFiles),
            });
            els.profileBadge.textContent = state.settings.profileName || state.settings.template || "default";
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
        }

        async function loadConversations() {
            try {
                const data = await apiRequest("/chat/conversations");
                state.conversations = data.conversations || [];
                renderConversations();
                ensureConversationSidebarRendered();
            } catch (error) {
                console.error("Failed to load conversations:", error);
                state.conversations = [];
                renderConversations();
                ensureConversationSidebarRendered();
            }
        }

        function getSettingsPanelOpen() {
            return els.settingsPanel.style.display !== "none";
        }

        function toggleSettingsPanel(forceState) {
            const shouldOpen = typeof forceState === "boolean" ? forceState : !getSettingsPanelOpen();
            els.settingsPanel.style.display = shouldOpen ? "block" : "none";
        }

        function applyActivationSettings(activation) {
            if (!activation || typeof activation !== "object") {
                return;
            }
            const tokenInput = document.getElementById("act-token");
            const apiUrlInput = document.getElementById("act-api-url");
            const statusEl = document.getElementById("act-status");
            if (tokenInput && activation.token) {
                tokenInput.value = activation.token;
            }
            if (apiUrlInput && activation.apiUrl) {
                apiUrlInput.value = activation.apiUrl;
            }
            document.getElementById("activation-panel").style.display = "flex";
            if (statusEl) {
                statusEl.innerHTML = '<span class="text-info">ØªÙ… Ø§Ø³ØªÙ„Ø§Ù… Ø±Ø§Ø¨Ø· Ø§Ù„ØªÙØ¹ÙŠÙ„. Ø£ÙƒÙ…Ù„ ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø¯Ø®ÙˆÙ„ Ù…Ù† Ù‡Ù†Ø§.</span>';
            }
        }

        async function toggleChatsCollapsed() {
            state.settings.chatsCollapsed = !state.settings.chatsCollapsed;
            renderConversations();
            await persistSettings();
        }

        async function toggleProjectsCollapsed() {
            state.settings.projectsCollapsed = !state.settings.projectsCollapsed;
            renderConversations();
            await persistSettings();
        }

        async function toggleShowAllChats() {
            state.settings.showAllChats = !state.settings.showAllChats;
            renderConversations();
            await persistSettings();
        }

        function renderChevron(expanded) {
            return `
                <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="${expanded ? "M5 8L10 13L15 8" : "M8 5L13 10L8 15"}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
                </svg>
            `;
        }

        function setSwipedProject(projectId) {
            state.swipedProjectId = projectId;
            renderConversations();
        }

        async function handleProjectHeaderClick(projectId) {
            const project = state.projects.find((item) => item.id === projectId);
            if (!project) {
                return;
            }
            if (state.swipedProjectId === projectId) {
                setSwipedProject(null);
                return;
            }
            state.currentProjectId = projectId;
            project.lastOpenedAt = new Date().toISOString();
            project.expanded = !project.expanded;
            syncCurrentProjectContext();
            updateComposerStatus(`${t("contextPrefix")} ${project.name}`);
            await refreshProjectFiles();
            await saveProjectState();
        }

        async function toggleLanguage() {
            state.settings.locale = getLocale() === "ar" ? "en" : "ar";
            applyLocale();
            renderConversations();
            await persistSettings();
        }

        function renderConversations() {
            els.conversationsList.innerHTML = state.conversations.map((conversation) => `
                <div class="conversation-item ${state.currentConversation === conversation.conversation_id ? "active" : ""}" data-id="${conversation.conversation_id}">
                    <div class="text-truncate">${conversation.title || "Ù…Ø­Ø§Ø¯Ø«Ø©"}</div>
                    <small class="text-muted" style="font-size:0.7rem">${new Date(conversation.created_at).toLocaleDateString("ar")}</small>
                </div>
            `).join("");

            document.querySelectorAll(".conversation-item").forEach((element) => {
                element.addEventListener("click", () => {
                    void loadConversation(element.dataset.id);
                });
            });
        }

        function handleProjectSwipeGesture(event) {
            if (!state.projectSwipeTracker) {
                return;
            }
            const { projectId, startX } = state.projectSwipeTracker;
            const deltaX = event.clientX - startX;
            state.projectSwipeTracker = null;
            if (deltaX < -40) {
                state.swipedProjectId = projectId;
                renderConversations();
                return;
            }
            if (deltaX > 40 && state.swipedProjectId === projectId) {
                state.swipedProjectId = null;
                renderConversations();
            }
        }

        function renderConversations() {
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
                : `<button class="empty-project-btn" id="btn-add-project-empty" type="button">${t("projects")} (${t("addProject")})</button>`;

            els.conversationsList.innerHTML = `
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-chats-section" type="button">
                        <span>${t("chats")}</span>
                        <span class="collapse-arrow">${renderChevron(!state.settings.chatsCollapsed)}</span>
                    </button>
                    <button class="section-add-btn" id="sidebar-new-chat" type="button" title="${t("newChat")}">
                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
                        </svg>
                        <span>${t("newChat")}</span>
                    </button>
                </div>
                ${generalSessions.length > 0 ? `
                    ${state.settings.chatsCollapsed ? "" : `
                        <div class="sidebar-group">
                            ${visibleGeneralSessions.map((conversation) => renderConversationButton(conversation)).join("")}
                            ${generalSessions.length > MAX_VISIBLE_GENERAL_SESSIONS ? `
                                <button class="show-more-btn" id="btn-toggle-all-chats" type="button">
                                    ${state.settings.showAllChats ? t("showLess") : t("showMore")}
                                </button>
                            ` : ""}
                        </div>
                    `}
                ` : ""}
                <div class="section-divider"></div>
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-projects-section" type="button">
                        <span>${t("projects")}</span>
                        <span class="collapse-arrow">${renderChevron(!state.settings.projectsCollapsed)}</span>
                    </button>
                    <button class="section-add-btn" id="btn-add-project" type="button" title="${t("openDirectory")}">
                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M3 7.5C3 6.12 4.12 5 5.5 5H9L11 7H18.5C19.88 7 21 8.12 21 9.5V16.5C21 17.88 19.88 19 18.5 19H5.5C4.12 19 3 17.88 3 16.5V7.5Z" fill="currentColor"></path>
                        </svg>
                        <span>${t("openDirectory")}</span>
                    </button>
                </div>
                ${state.settings.projectsCollapsed ? "" : `<div class="sidebar-group">${projectsHtml}</div>`}
            `;

            document.getElementById("sidebar-new-chat")?.addEventListener("click", () => {
                newConversation();
            });
            document.getElementById("toggle-chats-section")?.addEventListener("click", (event) => {
                void toggleChatsCollapsed();
            });
            document.getElementById("toggle-projects-section")?.addEventListener("click", (event) => {
                void toggleProjectsCollapsed();
            });
            document.getElementById("btn-toggle-all-chats")?.addEventListener("click", () => {
                void toggleShowAllChats();
            });
            document.getElementById("btn-add-project")?.addEventListener("click", () => {
                void promptAndAddProject();
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
        }

        async function loadConversation(id) {
            state.currentConversation = id;
            state.currentMessages = [];
            renderConversations();
            els.welcomeScreen.style.display = "none";
            els.chatBody.innerHTML = "";

            try {
                const data = await apiRequest(`/chat/conversations/${id}/messages`);
                state.currentMessages = data.messages || [];
                state.currentMessages.forEach((message) => appendMessage(message.role, message.content));
                scrollBottom();
            } catch (error) {
                console.error("Failed to load messages:", error);
            }
        }

        function newConversation() {
            state.currentConversation = null;
            state.currentMessages = [];
            els.chatBody.innerHTML = "";
            els.welcomeScreen.style.display = "block";
            els.chatTitle.textContent = "Ù…Ø­Ø§Ø¯Ø«Ø© Ø¬Ø¯ÙŠØ¯Ø©";
            resetStreamingState();
            renderConversations();
        }

        function renderConversationButton(conversation, className = "general-session-item") {
            const activeClass = state.currentConversation === conversation.conversation_id ? "active" : "";
            return `
                <button class="${className} ${activeClass}" data-conversation-id="${conversation.conversation_id}" type="button">
                    <div class="text-truncate">${escapeHtml(conversation.title || t("newChat"))}</div>
                    <span class="project-session-meta">${new Date(conversation.created_at).toLocaleDateString("ar")}</span>
                </button>
            `;
        }

        function renderConversations() {
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
                        <div class="project-item">
                            <div class="project-header">
                                <button class="project-title-btn ${state.currentProjectId === project.id ? "active" : ""}" data-project-id="${project.id}" type="button">
                                    <div class="project-name text-truncate">${escapeHtml(project.name)}</div>
                                    <span class="project-path">${escapeHtml(project.path)}</span>
                                </button>
                                <button class="project-action-btn" data-project-session="${project.id}" type="button" title="${t("projectNewSession")}">
                                    <i class="bi bi-plus-lg"></i>
                                </button>
                                <button class="project-action-btn" data-project-toggle="${project.id}" type="button" title="${project.expanded ? t("hideSessions") : t("showSessions")}">
                                    <span class="collapse-arrow">${project.expanded ? "â–¾" : "â–¸"}</span>
                                </button>
                                <button class="project-action-btn" data-project-delete="${project.id}" type="button" title="${t("deleteProject")}">
                                    <i class="bi bi-trash"></i>
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
                    `;
                }).join("")
                : `<button class="empty-project-btn" id="btn-add-project-empty" type="button">${t("projects")} (${t("addProject")})</button>`;

            els.conversationsList.innerHTML = `
                <button class="btn btn-sm btn-primary-custom sidebar-action-btn" id="sidebar-new-chat" type="button">
                    + ${t("newChat")}
                </button>
                ${generalSessions.length > 0 ? `
                    <div class="section-toggle-row">
                        <button class="section-toggle-btn" id="toggle-chats-section" type="button">
                            <span>${t("chats")}</span>
                            <span class="collapse-arrow">${state.settings.chatsCollapsed ? "â–¸" : "â–¾"}</span>
                        </button>
                    </div>
                    ${state.settings.chatsCollapsed ? "" : `
                        <div class="sidebar-group">
                            ${visibleGeneralSessions.map((conversation) => renderConversationButton(conversation)).join("")}
                            ${generalSessions.length > MAX_VISIBLE_GENERAL_SESSIONS ? `
                                <button class="show-more-btn" id="btn-toggle-all-chats" type="button">
                                    ${state.settings.showAllChats ? t("showLess") : t("showMore")}
                                </button>
                            ` : ""}
                        </div>
                    `}
                ` : ""}
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-projects-section" type="button">
                        <span>${t("projects")}</span>
                        <span class="collapse-arrow">${state.settings.projectsCollapsed ? "â–¸" : "â–¾"}</span>
                    </button>
                    <button class="project-action-btn" id="btn-add-project" type="button" title="${t("openDirectory")}">
                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M3 7.5C3 6.12 4.12 5 5.5 5H9L11 7H18.5C19.88 7 21 8.12 21 9.5V16.5C21 17.88 19.88 19 18.5 19H5.5C4.12 19 3 17.88 3 16.5V7.5Z" fill="currentColor"></path>
                        </svg>
                    </button>
                </div>
                ${state.settings.projectsCollapsed ? "" : `<div class="sidebar-group">${projectsHtml}</div>`}
            `;

            document.getElementById("sidebar-new-chat")?.addEventListener("click", () => {
                newConversation();
            });
            document.getElementById("toggle-chats-section")?.addEventListener("click", () => {
                void toggleChatsCollapsed();
            });
            document.getElementById("toggle-projects-section")?.addEventListener("click", () => {
                void toggleProjectsCollapsed();
            });
            document.getElementById("btn-toggle-all-chats")?.addEventListener("click", () => {
                void toggleShowAllChats();
            });
            document.getElementById("btn-add-project")?.addEventListener("click", () => {
                void promptAndAddProject();
            });
            document.getElementById("btn-add-project-empty")?.addEventListener("click", () => {
                void promptAndAddProject();
            });
            document.querySelectorAll("[data-conversation-id]").forEach((element) => {
                element.addEventListener("click", () => {
                    void loadConversation(element.dataset.conversationId);
                });
            });
            document.querySelectorAll("[data-project-id]").forEach((element) => {
                element.addEventListener("click", () => {
                    void selectProject(element.dataset.projectId);
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
            document.querySelectorAll("[data-project-toggle]").forEach((element) => {
                element.addEventListener("click", () => {
                    void toggleProjectExpanded(element.dataset.projectToggle);
                });
            });
            document.querySelectorAll("[data-project-show-more]").forEach((element) => {
                element.addEventListener("click", () => {
                    void toggleProjectShowMore(element.dataset.projectShowMore);
                });
            });
        }

        async function loadConversation(id) {
            state.currentConversation = id;
            state.conversationResetPending = false;
            state.currentMessages = [];
            updateProjectSelectionFromConversation(id);
            const conversation = state.conversations.find((item) => item.conversation_id === id);
            els.chatTitle.textContent = conversation?.title || getCurrentProject()?.name || t("newChat");
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
                state.currentMessages.forEach((message) => appendMessage(message.role, message.content));
                scrollBottom();
            } catch (error) {
                console.error("Failed to load messages:", error);
            }
        }

        function newConversation() {
            state.currentProjectId = null;
            syncCurrentProjectContext();
            state.currentConversation = null;
            state.conversationResetPending = true;
            state.currentMessages = [];
            els.chatBody.innerHTML = "";
            els.welcomeScreen.style.display = "block";
            els.chatTitle.textContent = t("newChat");
            resetStreamingState();
            updateComposerStatus(`${t("contextPrefix")} ${t("regularChat")} - ${t("noProject")}`);
            renderConversations();
            void refreshProjectFiles();
        }

        async function selectProject(projectId) {
            state.currentProjectId = projectId;
            const project = getCurrentProject();
            if (!project) {
                return;
            }
            project.lastOpenedAt = new Date().toISOString();
            syncCurrentProjectContext();
            updateComposerStatus(`${t("contextPrefix")} ${project.name}`);
            await refreshProjectFiles();
            await saveProjectState();
        }

        async function startProjectSession(projectId) {
            await selectProject(projectId);
            state.currentConversation = null;
            state.conversationResetPending = true;
            state.currentMessages = [];
            els.chatBody.innerHTML = "";
            els.welcomeScreen.style.display = "block";
            els.chatTitle.textContent = getCurrentProject()?.name || "Ù…Ø­Ø§Ø¯Ø«Ø© Ù…Ø´Ø±ÙˆØ¹";
            resetStreamingState();
            renderConversations();
        }

        async function toggleProjectExpanded(projectId) {
            const project = state.projects.find((item) => item.id === projectId);
            if (!project) {
                return;
            }
            project.expanded = !project.expanded;
            await saveProjectState();
        }

        async function toggleProjectShowMore(projectId) {
            const project = state.projects.find((item) => item.id === projectId);
            if (!project) {
                return;
            }
            project.showAllSessions = !project.showAllSessions;
            await saveProjectState();
        }

        async function deleteProject(projectId) {
            const project = state.projects.find((item) => item.id === projectId);
            if (!project) {
                return;
            }
            const confirmed = window.confirm(`Ø­Ø°Ù Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ ${project.name} Ù…Ù† Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø¯ÙŠØ³ÙƒØªÙˆØ¨ØŸ Ù„Ù† ÙŠØªÙ… Ø­Ø°Ù Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø¬Ù„Ø¯.`);
            if (!confirmed) {
                return;
            }

            state.projects = state.projects.filter((item) => item.id !== projectId);
            Object.keys(state.conversationProjectMap).forEach((conversationId) => {
                if (state.conversationProjectMap[conversationId] === projectId) {
                    delete state.conversationProjectMap[conversationId];
                }
            });
            if (state.currentProjectId === projectId) {
                state.currentProjectId = null;
                syncCurrentProjectContext();
                void refreshProjectFiles();
            }
            await saveProjectState();
        }

        async function deleteProject(projectId) {
            const project = state.projects.find((item) => item.id === projectId);
            if (!project) {
                return;
            }
            const confirmed = window.confirm(`Ù‡Ù„ Ø£Ù†Øª Ù…ØªØ£ÙƒØ¯ Ù…Ù† Ø­Ø°Ù Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ ${project.name} Ù…Ù† Ù‚Ø§Ø¦Ù…Ø© Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ØŸ Ù„Ù† ÙŠØªÙ… Ø­Ø°Ù Ø£ÙŠ Ù…Ù„Ù Ù…Ù† Ø¬Ù‡Ø§Ø² Ø§Ù„ÙƒÙ…Ø¨ÙŠÙˆØªØ±.`);
            if (!confirmed) {
                state.swipedProjectId = null;
                renderConversations();
                return;
            }

            state.projects = state.projects.filter((item) => item.id !== projectId);
            Object.keys(state.conversationProjectMap).forEach((conversationId) => {
                if (state.conversationProjectMap[conversationId] === projectId) {
                    delete state.conversationProjectMap[conversationId];
                }
            });
            if (state.currentProjectId === projectId) {
                state.currentProjectId = null;
                syncCurrentProjectContext();
                void refreshProjectFiles();
            }
            state.swipedProjectId = null;
            await saveProjectState();
        }

        async function promptAndAddProject() {
            const folderPath = await window.electronAPI.openFolder();
            if (!folderPath) {
                return;
            }

            const existingProject = state.projects.find((project) => project.path === folderPath);
            if (existingProject) {
                await selectProject(existingProject.id);
                return;
            }

            const project = {
                id: `project-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                name: folderPath.split(/[\\/]/).pop() || "Project",
                path: folderPath,
                selectedFiles: [],
                createdAt: new Date().toISOString(),
                lastOpenedAt: new Date().toISOString(),
                expanded: true,
                showAllSessions: false,
            };
            state.projects.unshift(project);
            state.currentProjectId = project.id;
            syncCurrentProjectContext();
            await saveProjectState();
            await refreshProjectFiles();
            updateComposerStatus(`ØªÙ… ÙØªØ­ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹: ${project.name}`);
        }

        async function getWebSocketToken() {
            try {
                const data = await apiRequest("/auth/ws-token", { method: "POST" });
                state.authRequired = false;
                return data.access_token || state.settings.token;
            } catch (error) {
                if (/Invalid or expired token|Token has been revoked|Missing auth token|inactive/i.test(error.message || "")) {
                    await handleAuthFailure("Ø§Ù„Ø¬Ù„Ø³Ø© Ù…Ù†ØªÙ‡ÙŠØ© Ø£Ùˆ ØºÙŠØ± ØµØ§Ù„Ø­Ø©. Ø£Ø¹Ø¯ Ø§Ù„ØªÙØ¹ÙŠÙ„ Ø£Ùˆ Ø­Ø¯Ù‘Ø« Ø±Ù…Ø² Ø§Ù„Ø¯Ø®ÙˆÙ„ Ø£ÙˆÙ„Ø§Ù‹.");
                    throw error;
                }
                console.warn("Failed to create a WebSocket token:", error.message);
                return state.settings.token;
            }
        }

        async function connectWebSocket() {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                return;
            }
            if (state.ws && state.ws.readyState === WebSocket.CONNECTING) {
                return;
            }
            if (!state.settings.token || state.authRequired) {
                return;
            }

            const apiUrl = new URL(state.settings.apiUrl || "http://localhost:8002/api");
            const wsProtocol = apiUrl.protocol === "https:" ? "wss" : "ws";
            const apiPath = apiUrl.pathname.replace(/\/$/, "");
            const pathPrefix = apiPath.endsWith("/api") ? apiPath.slice(0, -4) : apiPath;
            const template = state.settings.template || "default";
            const profileName = state.settings.profileName || "";
            let wsToken = "";
            try {
                wsToken = await getWebSocketToken();
            } catch {
                return;
            }
            if (!wsToken) {
                return;
            }
            const params = new URLSearchParams({
                token: wsToken,
                agent_template_name: template,
            });
            if (profileName) {
                params.set("profile_name", profileName);
            }
            const wsUrl = `${wsProtocol}://${apiUrl.host}${pathPrefix}/api/chat/ws/chat?${params.toString()}`;

            state.ws = new WebSocket(wsUrl);

            state.ws.onopen = async () => {
                if (state.heartbeatInterval) {
                    clearInterval(state.heartbeatInterval);
                }
                state.heartbeatInterval = setInterval(() => {
                    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                        state.ws.send(JSON.stringify({ type: "heartbeat" }));
                    }
                }, 30000);

                await flushQueuedMessages();
            };

            state.ws.onmessage = (event) => {
                try {
                    handleWsMessage(JSON.parse(event.data));
                } catch (error) {
                    console.error("WebSocket parse error:", error);
                }
            };

            state.ws.onclose = (event) => {
                resetStreamingState();
                if (state.heartbeatInterval) {
                    clearInterval(state.heartbeatInterval);
                    state.heartbeatInterval = null;
                }
                state.ws = null;
                if (event.code === 4001 || event.code === 1008 || /Authentication failed/i.test(event.reason || "")) {
                    void handleAuthFailure("ÙØ´Ù„ Ø§ØªØµØ§Ù„ Ø§Ù„Ø¯Ø³ÙƒØªÙˆØ¨ Ù„Ø£Ù† Ø¬Ù„Ø³Ø© Ø§Ù„Ø¯Ø®ÙˆÙ„ Ù„Ù… ØªØ¹Ø¯ ØµØ§Ù„Ø­Ø©.");
                    return;
                }
                setTimeout(() => {
                    void connectWebSocket();
                }, 3000);
            };

            state.ws.onerror = (error) => {
                console.error("WebSocket error:", error);
            };
        }

        function buildWorkspaceDescriptor() {
            return {
                root_name: state.projectPath ? state.projectPath.split(/[\\/]/).pop() : "",
                selected_files: Array.from(state.selectedProjectFiles),
            };
        }

        async function sendToolResult(requestId, tool, ok, result, error = "") {
            if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
                throw new Error("WebSocket is not connected");
            }
            state.ws.send(JSON.stringify({
                type: "tool_result",
                request_id: requestId,
                tool,
                ok,
                result: result || undefined,
                error: error || undefined,
            }));
        }

        async function sendApplyResult(requestId, ok, result, error = "") {
            if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
                throw new Error("WebSocket is not connected");
            }
            state.ws.send(JSON.stringify({
                type: "apply_result",
                request_id: requestId,
                ok,
                result: result || undefined,
                error: error || undefined,
            }));
        }

        async function executeToolRequest(data) {
            if (!state.projectPath) {
                await sendToolResult(data.request_id, data.tool, false, null, "No local workspace is selected in the desktop app.");
                return;
            }

            try {
                let result;
                switch (data.tool) {
                    case "list_files":
                        result = await window.electronAPI.listFiles(state.projectPath, data.args || {});
                        break;
                    case "search_files":
                        result = await window.electronAPI.searchFiles(
                            state.projectPath,
                            (data.args && data.args.query) || "",
                            (data.args && data.args.limit) || 20,
                        );
                        break;
                    case "read_file":
                        result = await window.electronAPI.readFile(state.projectPath, data.args && data.args.path);
                        break;
                    case "read_multiple_files":
                        result = await window.electronAPI.readMultipleFiles(
                            state.projectPath,
                            (data.args && data.args.paths) || [],
                        );
                        break;
                    default:
                        throw new Error(`Unsupported local tool: ${data.tool}`);
                }

                if (result && result.error) {
                    await sendToolResult(data.request_id, data.tool, false, null, result.error);
                    appendSystemMessage(`ÙØ´Ù„ ØªÙ†ÙÙŠØ° ${data.tool}: ${result.error}`);
                    return;
                }

                await sendToolResult(data.request_id, data.tool, true, result, "");
            } catch (error) {
                await sendToolResult(data.request_id, data.tool, false, null, error.message);
                appendSystemMessage(`ÙØ´Ù„ ØªÙ†ÙÙŠØ° ${data.tool}: ${error.message}`);
            }
        }

        async function executeApplyRequest(data) {
            if (!state.projectPath) {
                await sendApplyResult(data.request_id, false, null, "No local workspace is selected in the desktop app.");
                return;
            }

            try {
                const preview = await window.electronAPI.prepareWorkspaceChanges(state.projectPath, data.changes || []);
                if (preview.error) {
                    await sendApplyResult(data.request_id, false, null, preview.error);
                    appendSystemMessage(`ØªØ¹Ø°Ø± ØªØ¬Ù‡ÙŠØ² Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª: ${preview.error}`);
                    return;
                }

                const summary = data.summary || "Hermes proposed workspace changes.";
                const details = [
                    summary,
                    `Operations: ${preview.summary.totalOperations || 0}`,
                    `Changed lines: ${preview.summary.changedLines || 0}`,
                    `Changed files: ${(preview.summary.changedFiles || []).join(", ") || "-"}`,
                    `Created files: ${(preview.summary.createdFiles || []).join(", ") || "-"}`,
                    `Renamed files: ${(preview.summary.renamedFiles || []).map((item) => `${item.from} -> ${item.to}`).join(", ") || "-"}`,
                    `Deleted files: ${(preview.summary.deletedFiles || []).join(", ") || "-"}`,
                    "",
                    "Approve these local changes?",
                ].join("\n");

                const approved = window.confirm(details);
                if (!approved) {
                    await sendApplyResult(data.request_id, false, { approved: false }, "User rejected the proposed workspace changes.");
                    appendSystemMessage("ØªÙ… Ø±ÙØ¶ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª Ø§Ù„Ù…Ø­Ù„ÙŠØ© Ø§Ù„Ù…Ù‚ØªØ±Ø­Ø©.");
                    return;
                }

                const applied = await window.electronAPI.applyWorkspaceChanges(preview.previewToken);
                if (applied.error) {
                    await sendApplyResult(data.request_id, false, null, applied.error);
                    appendSystemMessage(`ÙØ´Ù„ ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª: ${applied.error}`);
                    return;
                }

                await refreshProjectFiles();
                await sendApplyResult(data.request_id, true, {
                    approved: true,
                    changed_files: applied.changedFiles || [],
                    summary,
                }, "");
                appendSystemMessage("ØªÙ… ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª Ø§Ù„Ù…Ø­Ù„ÙŠØ© Ø¨Ø¹Ø¯ Ø§Ù„Ù…ÙˆØ§ÙÙ‚Ø©.");
            } catch (error) {
                await sendApplyResult(data.request_id, false, null, error.message);
                appendSystemMessage(`ÙØ´Ù„ ØªØ·Ø¨ÙŠÙ‚ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª: ${error.message}`);
            }
        }

        function extractInlineArtifact(content) {
            const text = String(content || "");
            const fencedMatch = text.match(/(?:^|\r?\n)\s*Filename:\s*([^\r\n]+)\s*\r?\n\s*\r?\n?\s*```([a-zA-Z0-9_-]*)\r?\n([\s\S]*?)\r?\n```/);
            if (fencedMatch) {
                return {
                    fileName: fencedMatch[1].trim(),
                    body: fencedMatch[3],
                };
            }
            const markdownMatch = text.match(/(?:^|\r?\n)\s*(?:\*\*)?(?:Filename|اسم الملف|الملف)(?:\*\*)?\s*:\s*`?([^\r\n`]+)`?[\s\S]*?```(?:[a-zA-Z0-9_-]*)?\r?\n([\s\S]*?)\r?\n```/i);
            if (markdownMatch) {
                return {
                    fileName: markdownMatch[1].trim(),
                    body: markdownMatch[2],
                };
            }
            const inlineMatch = text.match(/inline:([^\r\n:]+):\r?\n([\s\S]*?)\r?\n:end:inline:/i);
            if (inlineMatch) {
                return {
                    fileName: inlineMatch[1].trim(),
                    body: inlineMatch[2],
                };
            }
            const sectionMatch = text.match(/(?:^|\r?\n)\s*(?:Filename|اسم الملف)\s*:\s*([^\r\n]+)[\s\S]*?(?:Content|المحتوى)\s*:\s*\r?\n\r?\n?([\s\S]*?)(?:\r?\n(?:\r?\n)?---|\s*$)/i);
            if (sectionMatch) {
                return {
                    fileName: sectionMatch[1].trim(),
                    body: sectionMatch[2].trimEnd(),
                };
            }
            return null;
        }
        function normalizeArtifactFileName(fileName) {
            return String(fileName || "")
                .replace(/[*`]+/g, "")
                .replace(/^[:\-\s]+|[:\-\s]+$/g, "")
                .trim();
        }

        function normalizeArtifactBody(body) {
            const text = String(body || "").replace(/\r\n/g, "\n");
            const advisorySplit = text.split(/\n{2,}(?=To proceed|To actually save|You can copy|If you want|للمتابعة|لحفظ الملف|يمكنك النسخ|إذا أردت)/i);
            return advisorySplit[0].trimEnd();
        }
        function unwrapAssistantFinalEnvelope(content) {
            const text = String(content || "").trim();
            if (!text.startsWith("{")) {
                return text;
            }
            try {
                const parsed = JSON.parse(text);
                if (parsed && parsed.type === "assistant_final" && typeof parsed.content === "string" && parsed.content.trim()) {
                    return parsed.content.trim();
                }
            } catch {}
            return text;
        }

        async function saveInlineArtifactFromAssistant(content) {
            if (!window.electronAPI?.saveConversationArtifact || state.projectPath) {
                return;
            }
            const artifact = extractInlineArtifact(content);
            if (!artifact || !artifact.fileName) {
                return;
            }
            const normalizedFileName = normalizeArtifactFileName(artifact.fileName);
            const normalizedBody = normalizeArtifactBody(artifact.body);
            if (!normalizedFileName || !normalizedBody) {
                return;
            }
            const artifactKey = `${normalizedFileName}
${normalizedBody}`;
            if (state.savedArtifactKeys.has(artifactKey)) {
                return;
            }
            const result = await window.electronAPI.saveConversationArtifact(normalizedFileName, normalizedBody);
            if (!result?.ok) {
                appendSystemMessage(`???? ??? ????? ??????: ${result?.error || "Unknown error"}`);
                return;
            }
            state.savedArtifactKeys.add(artifactKey);
            appendSystemMessage(`?? ??? ????? ???????? ?? ${result.path}`);
        }

        function getLatestAssistantMessageText() {
            const assistantMessages = Array.from(document.querySelectorAll(".message.assistant"));
            const latest = assistantMessages[assistantMessages.length - 1];
            return latest ? latest.innerText.replace(/\n\d{1,2}:\d{2}:\d{2}\s*[^\n]*$/u, "").trim() : "";
        }
        function handleWsMessage(data) {
            switch (data.type) {
                case "start":
                    startAssistantStream();
                    if (data.conversation_id && !state.currentConversation) {
                        state.currentConversation = data.conversation_id;
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
                        state.currentConversation = data.conversation_id;
                    }
                    void loadConversations();
                    break;
                case "error":
                    resetStreamingState();
                    appendSystemMessage(`خطأ: ${data.detail}`);
                    break;
                default:
                    break;
            }
        }

        async function buildProjectContextForMessage(text) {
            if (!state.projectPath) {
                els.contextStatus.textContent = "Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ù…Ø¬Ù„Ø¯ Ù…Ø´Ø±ÙˆØ¹ Ù…Ø­Ø¯Ø¯.";
                return "";
            }

            const result = await window.electronAPI.buildProjectContext(
                state.projectPath,
                text,
                Array.from(state.selectedProjectFiles),
            );

            if (result.error) {
                els.contextStatus.textContent = result.error;
                return "";
            }

            els.contextStatus.textContent = result.files.length > 0
                ? `ØªÙ… Ø¥Ø±ÙØ§Ù‚ ${result.files.length} Ù…Ù„Ù/Ù…Ù‚Ø·Ø¹ Ù…Ù†Ø§Ø³Ø¨ Ù…Ø¹ Ø§Ù„Ø±Ø³Ø§Ù„Ø©.`
                : "Ù„Ù… ÙŠØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ Ù…Ù‚Ø§Ø·Ø¹ Ù…Ù†Ø§Ø³Ø¨Ø© Ù…Ù† Ø§Ù„Ù…Ø´Ø±ÙˆØ¹.";
            return result.context || "";
        }

        async function sendWebSocketMessage(text, profileNameOverride = "") {
            const projectContext = await buildProjectContextForMessage(text);
            const selectedProfileName = profileNameOverride || state.settings.profileName || undefined;
            const payload = {
                type: "user_message",
                content: text,
                project_context: projectContext || undefined,
                profile_name: selectedProfileName,
                workspace: buildWorkspaceDescriptor(),
            };

            state.ws.send(JSON.stringify(payload));
        }

        async function waitForWebSocketOpen(timeoutMs = 4000) {
            if (state.authRequired || !state.settings.token) {
                return false;
            }
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                return true;
            }

            await connectWebSocket();
            if (!state.ws) {
                return false;
            }
            if (state.ws.readyState === WebSocket.OPEN) {
                return true;
            }

            return await new Promise((resolve) => {
                const ws = state.ws;
                let settled = false;
                const finish = (value) => {
                    if (settled) {
                        return;
                    }
                    settled = true;
                    clearTimeout(timer);
                    ws.removeEventListener("open", handleOpen);
                    ws.removeEventListener("close", handleClose);
                    ws.removeEventListener("error", handleError);
                    resolve(value);
                };
                const handleOpen = () => finish(true);
                const handleClose = () => finish(false);
                const handleError = () => finish(false);
                const timer = setTimeout(() => finish(false), timeoutMs);

                ws.addEventListener("open", handleOpen, { once: true });
                ws.addEventListener("close", handleClose, { once: true });
                ws.addEventListener("error", handleError, { once: true });
            });
        }

        async function sendMessage() {
            const text = els.messageInput.value.trim();
            if (!text || state.isStreaming) {
                return;
            }
            if (state.authRequired || !state.settings.token) {
                await handleAuthFailure("Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø¥Ø±Ø³Ø§Ù„ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ù„Ø£Ù† Ø¬Ù„Ø³Ø© Ø§Ù„Ø¯Ø³ÙƒØªÙˆØ¨ ØºÙŠØ± ØµØ§Ù„Ø­Ø©.");
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
                appendSystemMessage(`ØªÙ… ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ queue Ø¨Ø¹Ø¯ ÙØ´Ù„ Ø§Ù„Ø¥Ø±Ø³Ø§Ù„: ${error.message}`);
            }
        }

        function renderProjectFiles() {
            els.selectedFilesStatus.textContent = `${state.selectedProjectFiles.size} Ù…Ù„Ù Ù…Ø­Ø¯Ø¯ ÙƒØ£ÙˆÙ„ÙˆÙŠØ© Ù„Ù„Ø³ÙŠØ§Ù‚`;
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
            if (!state.projectPath) {
                state.projectFiles = [];
                renderProjectFiles();
                return;
            }

            const result = await window.electronAPI.scanFolder(state.projectPath);
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
            els.writePreviewStatus.textContent = `ØªÙ… ØªØ­Ù…ÙŠÙ„ Ø§Ù„Ù…Ù„Ù (${(result.size / 1024).toFixed(1)} KB)`;
        }

        async function prepareFileWrite() {
            if (!state.projectPath || !state.currentFilePath) {
                els.writePreviewStatus.textContent = "Ø§Ø®ØªØ± Ù…Ù„ÙØ§Ù‹ Ø£ÙˆÙ„Ø§Ù‹.";
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
            els.btnApplyWrite.disabled = true;
            els.writePreviewStatus.textContent = "ØªÙ… Ø­ÙØ¸ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„ Ø¨Ø¹Ø¯ Ø§Ù„Ù…ÙˆØ§ÙÙ‚Ø©.";
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
                appendSystemMessage(`ØªÙ… ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ queue Ø¨Ø¹Ø¯ ÙØ´Ù„ Ø§Ù„Ø¥Ø±Ø³Ø§Ù„: ${error.message}`);
            }
        }

        function renderProjectFiles() {
            const currentProject = getCurrentProject();
            els.selectedFilesStatus.textContent = currentProject
                ? `${state.selectedProjectFiles.size} Ù…Ù„Ù Ù…Ø­Ø¯Ø¯ Ù„Ù„Ù…Ø´Ø±ÙˆØ¹ ${currentProject.name}`
                : `${state.selectedProjectFiles.size} Ù…Ù„Ù Ù…Ø­Ø¯Ø¯ ÙƒØ£ÙˆÙ„ÙˆÙŠØ© Ù„Ù„Ø³ÙŠØ§Ù‚`;
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
            if (!state.projectPath) {
                state.projectFiles = [];
                renderProjectFiles();
                return;
            }

            const result = await window.electronAPI.scanFolder(state.projectPath);
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
                        <span style="display:inline-flex;align-items:center;gap:8px;"><span>ðŸ’¬</span><span>${t("chats")}</span></span>
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
                        <span style="display:inline-flex;align-items:center;gap:8px;"><span>ðŸ“</span><span>${t("projects")}</span></span>
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
        renderConversations = renderConversationsFixed;

        function ensureConversationSidebarRendered() {
            if (!els.conversationsList) {
                return;
            }
            const hasStructure = els.conversationsList.querySelector("#toggle-chats-section, #toggle-projects-section");
            const hasContent = els.conversationsList.textContent.trim().length > 0;
            if (!hasStructure || !hasContent) {
                renderConversationsFixed();
            }
        }

        async function toggleMicrophone() {
            if (state.speechRecognitionActive && state.speechRecognition) {
                state.speechRecognition.stop();
                return;
            }

            const SpeechRecognitionCtor = getSpeechRecognitionCtor();
            if (!SpeechRecognitionCtor) {
                updateComposerStatus("Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ø§Ù„ØµÙˆØªÙŠ ØºÙŠØ± Ù…Ø¯Ø¹ÙˆÙ… ÙÙŠ Ù‡Ø°Ø§ Ø§Ù„Ø¬Ù‡Ø§Ø².");
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach((track) => track.stop());
            } catch (error) {
                updateComposerStatus(`ÙØ´Ù„ Ø§Ù„ÙˆØµÙˆÙ„ Ø¥Ù„Ù‰ Ø§Ù„Ù…ÙŠÙƒØ±ÙˆÙÙˆÙ†: ${error.message}`);
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
                updateComposerStatus("Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø§Ø³ØªÙ…Ø§Ø¹...");
            };
            recognition.onresult = (event) => {
                const transcript = Array.from(event.results).map((result) => result[0]?.transcript || "").join(" ").trim();
                if (transcript) {
                    els.messageInput.value = `${els.messageInput.value} ${transcript}`.trim();
                    els.messageInput.dispatchEvent(new Event("input"));
                    updateComposerStatus("ØªÙ… Ø¥Ø¯Ø±Ø§Ø¬ Ø§Ù„Ù†Øµ Ø§Ù„ØµÙˆØªÙŠ ÙÙŠ Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø©.");
                }
            };
            recognition.onerror = (event) => {
                updateComposerStatus(`Ø®Ø·Ø£ ÙÙŠ Ø§Ù„ØªØ³Ø¬ÙŠÙ„ Ø§Ù„ØµÙˆØªÙŠ: ${event.error || "unknown"}`);
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
                statusEl.innerHTML = "<span class=\"text-danger\">Ø£Ø¯Ø®Ù„ ÙƒÙˆØ¯ Ø§Ù„Ø¯Ø¹ÙˆØ© ÙˆÙƒÙ„Ù…Ø© Ø§Ù„Ù…Ø±ÙˆØ±</span>";
                return;
            }

            statusEl.innerHTML = "<span class=\"text-info\">Ø¬Ø§Ø±Ù Ø§Ù„ØªÙØ¹ÙŠÙ„...</span>";

            try {
                const response = await fetch(`${apiUrl}/auth/activate`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ token, password }),
                });
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || "Failed to activate");
                }

                state.settings = await window.electronAPI.setSettings({
                    ...state.settings,
                    apiUrl,
                    token: data.access_token,
                    template: "default",
                });

                statusEl.innerHTML = "<span class=\"text-success\">ØªÙ… Ø§Ù„ØªÙØ¹ÙŠÙ„ Ø¨Ù†Ø¬Ø§Ø­</span>";
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

        window.electronAPI.onActivationLink?.((activation) => {
            applyActivationSettings(activation);
        });

        document.getElementById("btn-tg-gen-code").addEventListener("click", async () => {
            const codeInput = document.getElementById("tg-bind-code");
            const statusEl = document.getElementById("tg-bind-status");
            statusEl.innerHTML = "<span class=\"text-info\">Ø¬Ø§Ø±Ù Ø§Ù„ØªÙˆÙ„ÙŠØ¯...</span>";

            try {
                const data = await apiRequest("/telegram/generate-bind-code", { method: "POST" });
                if (data.bind_code) {
                    codeInput.value = data.bind_code;
                    statusEl.innerHTML = "<span class=\"text-success\">ØªÙ… ØªÙˆÙ„ÙŠØ¯ Ø§Ù„ÙƒÙˆØ¯. Ø£Ø±Ø³Ù„Ù‡ Ù„Ù„Ø¨ÙˆØª Ø«Ù… Ø§Ø¶ØºØ· ØªØ£ÙƒÙŠØ¯ Ø§Ù„Ø±Ø¨Ø·.</span>";
                } else {
                    statusEl.innerHTML = "<span class=\"text-warning\">Ø§Ù„Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¨ÙˆØ· Ø¨Ø§Ù„ÙØ¹Ù„.</span>";
                }
            } catch (error) {
                statusEl.innerHTML = `<span class="text-danger">خطأ: ${escapeHtml(error.message)}</span>`;
            }
        });

        document.getElementById("btn-tg-bind").addEventListener("click", async () => {
            const bindCode = document.getElementById("tg-bind-code").value.trim();
            const statusEl = document.getElementById("tg-bind-status");

            if (!bindCode) {
                statusEl.innerHTML = "<span class=\"text-danger\">ÙˆÙ„Ù‘Ø¯ Ø§Ù„ÙƒÙˆØ¯ Ø£ÙˆÙ„Ø§Ù‹</span>";
                return;
            }

            statusEl.innerHTML = "<span class=\"text-info\">Ø¬Ø§Ø±Ù Ø§Ù„ØªØ£ÙƒÙŠØ¯...</span>";

            try {
                await apiRequest("/telegram/bind-with-code", {
                    method: "POST",
                    body: JSON.stringify({ binding_code: bindCode }),
                });
                statusEl.innerHTML = "<span class=\"text-success\">ØªÙ… Ø§Ù„Ø±Ø¨Ø· Ø¨Ù†Ø¬Ø§Ø­.</span>";
            } catch (error) {
                statusEl.innerHTML = `<span class="text-danger">خطأ: ${escapeHtml(error.message)}</span>`;
            }
        });

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

        function setMessageElementContent(element, role, content) {
            const body = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
            const copyButton = role === "system" ? "" : `
                <button class="message-copy-btn" type="button" title="${t("copy")}">
                    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M9 9H19V19H9V9Z" stroke="currentColor" stroke-width="1.8"></path>
                        <path d="M5 15H4V5H14V6" stroke="currentColor" stroke-width="1.8"></path>
                    </svg>
                </button>
            `;
            element.innerHTML = `${copyButton}<div class="message-body">${body}</div><div class="timestamp">${new Date().toLocaleTimeString(getLocale())}</div>`;
            const copyTrigger = element.querySelector(".message-copy-btn");
            copyTrigger?.addEventListener("click", async (event) => {
                event.stopPropagation();
                await copyTextToClipboard(content);
            });
            if (role === "assistant" && content) {
                queueMicrotask(() => {
                    void saveInlineArtifactFromAssistant(element.innerText || content);
                });
            }
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
                    ? (getLocale() === "en" ? "Selected project files and recent activity are shown here." : "ØªØ¸Ù‡Ø± Ù‡Ù†Ø§ Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ø§Ù„Ù…Ø®ØªØ§Ø±Ø© ÙˆØ¢Ø®Ø± Ø§Ù„Ø£Ù†Ø´Ø·Ø©.")
                    : (getLocale() === "en" ? "Open a project to inspect files, or stay in chat mode and follow activity." : "Ø§ÙØªØ­ Ù…Ø´Ø±ÙˆØ¹Ø§Ù‹ Ù„Ø¹Ø±Ø¶ Ù…Ù„ÙØ§ØªÙ‡ØŒ Ø£Ùˆ Ø§Ø¨Ù‚ ÙÙŠ ÙˆØ¶Ø¹ Ø§Ù„Ù…Ø­Ø§Ø¯Ø«Ø© ÙˆØªØ§Ø¨Ø¹ Ø§Ù„Ù†Ø´Ø§Ø·.")
            );
            els.projectPath.textContent = currentProject?.path || (getLocale() === "en" ? "No project selected" : "Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ù…Ø´Ø±ÙˆØ¹ Ù…Ø­Ø¯Ø¯");
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
            toggle.innerHTML = `<span>${escapeHtml(title)}</span><span class="collapse-arrow">${section.classList.contains("collapsed") ? "â€º" : "âŒ„"}</span>`;
            const body = document.createElement("div");
            body.className = "settings-category-body";
            nodes.filter(Boolean).forEach((node) => body.appendChild(node));
            toggle.addEventListener("click", async () => {
                section.classList.toggle("collapsed");
                toggle.querySelector(".collapse-arrow").textContent = section.classList.contains("collapsed") ? "â€º" : "âŒ„";
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
            headerText.innerHTML = `<h5>${getLocale() === "en" ? "Settings" : "Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª"}</h5><div class="settings-inline-note">${getLocale() === "en" ? "Grouped controls with collapsible categories." : "Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª Ù…Ø±ØªØ¨Ø© Ø¶Ù…Ù† Ø£Ù‚Ø³Ø§Ù… Ù‚Ø§Ø¨Ù„Ø© Ù„Ù„Ø·ÙŠ."}</div>`;
            modalHeader.append(headerText, els.btnCloseSettings);

            const container = document.createElement("div");
            container.append(
                buildSettingsCategory(getLocale() === "en" ? "General" : "Ø¹Ø§Ù…", "general", generalNodes),
                buildSettingsCategory(getLocale() === "en" ? "Telegram" : "Ø±Ø¨Ø· Ø§Ù„ØªÙ„Ø¬Ø±Ø§Ù…", "telegram", telegramNodes),
                buildSettingsCategory(getLocale() === "en" ? "Files and changes" : "Ø§Ù„Ù…Ù„ÙØ§Øª ÙˆØ§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª", "workspace", workspaceNodes),
                buildSettingsCategory(getLocale() === "en" ? "System and execution" : "Ø§Ù„Ù†Ø¸Ø§Ù… ÙˆØ§Ù„ØªÙ†ÙÙŠØ°", "system", systemNodes),
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
            ensureUiSettings();
            els.settingApiUrl.value = state.settings.apiUrl || "http://localhost:8002/api";
            els.settingToken.value = state.settings.token || "";
            els.settingTemplate.value = state.settings.template || "default";
            els.settingLanguage && (els.settingLanguage.value = state.settings.locale || "ar");
            els.composerCommandSelect && (els.composerCommandSelect.value = state.settings.commandMode || "queue");
            els.composerApprovalSelect && (els.composerApprovalSelect.value = state.settings.approvalMode || "ask_for_approval");
            document.getElementById("act-api-url").value = state.settings.activationApiUrl || state.settings.apiUrl || "http://localhost:8002/api";
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
            ensureConversationSidebarRendered();
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
                els.projectFiles.innerHTML = `<div class="activity-empty">${currentProject ? (getLocale() === "en" ? "No files were loaded for this project." : "Ù„Ù… ÙŠØªÙ… ØªØ­Ù…ÙŠÙ„ Ù…Ù„ÙØ§Øª Ù„Ù‡Ø°Ø§ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ø¨Ø¹Ø¯.") : t("noActivity")}</div>`;
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
                                <span class="file-badge ${file.status === "new" ? "new" : "modified"}">${file.status === "new" ? (getLocale() === "en" ? "New" : "Ø¬Ø¯ÙŠØ¯") : (getLocale() === "en" ? "Modified" : "Ù…Ø¹Ø¯Ù„")}</span>
                                ${state.selectedProjectFiles.has(file.path) ? `<span class="file-badge selected">${getLocale() === "en" ? "Context" : "Ø¶Ù…Ù† Ø§Ù„Ø³ÙŠØ§Ù‚"}</span>` : ""}
                            </div>
                        </div>
                        <div class="d-flex gap-1">
                            <button class="btn btn-sm btn-outline-secondary btn-open-file" data-file-path="${file.path}" type="button">${getLocale() === "en" ? "Open" : "فتح"}</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-secondary"} btn-select-file" data-file-path="${file.path}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? (getLocale() === "en" ? "Selected" : "Ù…Ø­Ø¯Ø¯") : (getLocale() === "en" ? "Select" : "ØªØ­Ø¯ÙŠØ¯")}
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
            if (!state.projectPath) {
                state.projectFiles = [];
                renderProjectFiles();
                return;
            }
            const result = await window.electronAPI.scanFolder(state.projectPath);
            if (result.error) {
                els.projectFiles.innerHTML = `<div class="text-danger">${escapeHtml(result.error)}</div>`;
                renderContextSidebar();
                return;
            }
            state.projectFiles = result.files || [];
            renderProjectFiles();
        }

        function buildWorkspaceDescriptor() {
            return {
                root_name: state.projectPath ? state.projectPath.split(/[\\/]/).pop() : "",
                selected_files: Array.from(state.selectedProjectFiles),
                command_mode: els.composerCommandSelect?.value || state.settings.commandMode || "queue",
                approval_mode: els.composerApprovalSelect?.value || state.settings.approvalMode || "ask_for_approval",
            };
        }

        async function sendWebSocketMessage(text, profileNameOverride = "") {
            const projectContext = await buildProjectContextForMessage(text);
            const selectedProfileName = profileNameOverride || state.settings.profileName || undefined;
            const payload = {
                type: "user_message",
                content: text,
                project_context: projectContext || undefined,
                profile_name: selectedProfileName,
                command_mode: els.composerCommandSelect?.value || state.settings.commandMode || "queue",
                approval_mode: els.composerApprovalSelect?.value || state.settings.approvalMode || "ask_for_approval",
                conversation_id: state.conversationResetPending ? null : (state.currentConversation || null),
                workspace: buildWorkspaceDescriptor(),
            };
            state.ws.send(JSON.stringify(payload));
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
                    appendSystemMessage(`Ã˜Â®Ã˜Â·Ã˜Â£: ${data.detail}`);
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
                || value === "Ù…Ø­Ø§Ø¯Ø«Ø©"
                || value === "Ù…Ø­Ø§Ø¯Ø«Ø© Ø¬Ø¯ÙŠØ¯Ø©"
                || value === "Ù…Ø­Ø§Ø¯Ø«Ø© Ù…Ø´Ø±ÙˆØ¹";
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
                list_files: getLocale() === "en" ? "Reading project files..." : "Ø¬Ø§Ø±ÙŠ Ù‚Ø±Ø§Ø¡Ø© Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø´Ø±ÙˆØ¹...",
                read_file: getLocale() === "en" ? "Opening the requested file..." : "Ø¬Ø§Ø±ÙŠ ÙØªØ­ Ø§Ù„Ù…Ù„Ù Ø§Ù„Ù…Ø·Ù„ÙˆØ¨...",
                search_files: getLocale() === "en" ? "Searching inside project files..." : "Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø¨Ø­Ø« Ø¯Ø§Ø®Ù„ Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø´Ø±ÙˆØ¹...",
                run_command: getLocale() === "en" ? "Running a local command..." : "Ø¬Ø§Ø±ÙŠ ØªÙ†ÙÙŠØ° Ø£Ù…Ø± Ù…Ø­Ù„ÙŠ...",
                list_directory: getLocale() === "en" ? "Reading project folders..." : "Ø¬Ø§Ø±ÙŠ Ù‚Ø±Ø§Ø¡Ø© Ù…Ø¬Ù„Ø¯Ø§Øª Ø§Ù„Ù…Ø´Ø±ÙˆØ¹...",
            };
            return messages[key] || (getLocale() === "en" ? "Processing a local workspace action..." : "Ø¬Ø§Ø±ÙŠ ØªÙ†ÙÙŠØ° Ø¥Ø¬Ø±Ø§Ø¡ Ù…Ø­Ù„ÙŠ Ø¹Ù„Ù‰ Ù…Ø³Ø§Ø­Ø© Ø§Ù„Ø¹Ù…Ù„...");
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
                tree.innerHTML = `<div class="context-tree-folder"><div class="context-tree-folder-files">${getLocale() === "en" ? "No created or modified files yet." : "Ù„Ø§ ØªÙˆØ¬Ø¯ Ù…Ù„ÙØ§Øª Ø¬Ø¯ÙŠØ¯Ø© Ø£Ùˆ Ù…Ø¹Ø¯Ù„Ø© Ø¨Ø¹Ø¯."}</div></div>`;
                return;
            }
            const markup = outputFiles
                .map((file) => `
                    <div class="context-tree-folder">
                        <div class="context-tree-folder-name">${escapeHtml(file.path.split(/[\\/]+/).pop() || file.path)}</div>
                        <div class="context-tree-folder-files">
                            ${escapeHtml(file.path)} · ${(file.size / 1024).toFixed(1)} KB · ${new Date(file.modifiedAt).toLocaleDateString(getLocale())} · ${file.status === "new" ? (getLocale() === "en" ? "New" : "Ø¬Ø¯ÙŠØ¯") : (getLocale() === "en" ? "Modified" : "Ù…Ø¹Ø¯Ù„")}
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

        function renderContextSidebar() {
            applyStaticLayoutFixes();
            const currentProject = getCurrentProject();
            document.getElementById("context-panel-title")?.replaceChildren(t("projectContext"));
            document.getElementById("context-panel-subtitle")?.replaceChildren(currentProject?.path || "/");
            els.projectPath.textContent = currentProject?.path || (getLocale() === "en" ? "No project selected" : "Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ù…Ø´Ø±ÙˆØ¹ Ù…Ø­Ø¯Ø¯");
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
                els.projectFiles.innerHTML = `<div class="activity-empty">${currentProject ? (getLocale() === "en" ? "No files were loaded for this project." : "Ù„Ù… ÙŠØªÙ… ØªØ­Ù…ÙŠÙ„ Ù…Ù„ÙØ§Øª Ù„Ù‡Ø°Ø§ Ø§Ù„Ù…Ø´Ø±ÙˆØ¹ Ø¨Ø¹Ø¯.") : t("noActivity")}</div>`;
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
                                <span class="file-badge ${file.status === "new" ? "new" : "modified"}">${file.status === "new" ? (getLocale() === "en" ? "New" : "Ø¬Ø¯ÙŠØ¯") : (getLocale() === "en" ? "Modified" : "Ù…Ø¹Ø¯Ù„")}</span>
                                ${state.selectedProjectFiles.has(file.path) ? `<span class="file-badge selected">${getLocale() === "en" ? "Context" : "Ø¶Ù…Ù† Ø§Ù„Ø³ÙŠØ§Ù‚"}</span>` : ""}
                            </div>
                        </div>
                        <div class="file-action-group">
                            <button class="btn btn-sm btn-outline-secondary btn-open-file" data-file-path="${escapeHtml(file.path)}" type="button">${getLocale() === "en" ? "Open" : "فتح"}</button>
                            <button class="btn btn-sm ${state.selectedProjectFiles.has(file.path) ? "btn-primary-custom" : "btn-outline-secondary"} btn-select-file" data-file-path="${escapeHtml(file.path)}" type="button">
                                ${state.selectedProjectFiles.has(file.path) ? (getLocale() === "en" ? "Selected" : "Ù…Ø­Ø¯Ø¯") : (getLocale() === "en" ? "Select" : "ØªØ­Ø¯ÙŠØ¯")}
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
                                    <span class="project-tree-chevron">${isExpanded ? "â–¾" : "â–¸"}</span>
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
                            <span class="project-tree-chevron">â–¾</span>
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

        async function loadSettings() {
            state.settings = await window.electronAPI.getSettings();
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
                await handleAuthFailure("Ù„Ø§ ÙŠÙ…ÙƒÙ† Ø¥Ø±Ø³Ø§Ù„ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ù„Ø£Ù† Ø¬Ù„Ø³Ø© Ø§Ù„Ø¯Ø³ÙƒØªÙˆØ¨ ØºÙŠØ± ØµØ§Ù„Ø­Ø©.");
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
                appendSystemMessage(`ØªÙ… ØªØ­ÙˆÙŠÙ„ Ø§Ù„Ø±Ø³Ø§Ù„Ø© Ø¥Ù„Ù‰ queue Ø¨Ø¹Ø¯ ÙØ´Ù„ Ø§Ù„Ø¥Ø±Ø³Ø§Ù„: ${error.message}`);
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
                    {
                        const lastMessage = state.currentMessages[state.currentMessages.length - 1];
                        const rawAssistantContent = data.content
                            || (lastMessage?.role === "assistant" ? (lastMessage.content || "") : "")
                            || getLatestAssistantMessageText();
                        const assistantContent = unwrapAssistantFinalEnvelope(rawAssistantContent);
                        if (lastMessage?.role === "assistant" && assistantContent && assistantContent !== lastMessage.content) {
                            lastMessage.content = assistantContent;
                            if (state.streamingAssistantElement) {
                                setMessageElementContent(state.streamingAssistantElement, "assistant", assistantContent);
                            } else {
                                const assistantMessages = Array.from(document.querySelectorAll(".message.assistant"));
                                const latestAssistant = assistantMessages[assistantMessages.length - 1];
                                if (latestAssistant) {
                                    setMessageElementContent(latestAssistant, "assistant", assistantContent);
                                }
                            }
                        }
                        if (assistantContent) {
                            void saveInlineArtifactFromAssistant(assistantContent);
                        }
                    }
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
            renderConversations = renderConversationsFixed;
            await loadSettings();
            ensureConversationSidebarRendered();

            if (!state.settings.token) {
                document.getElementById("activation-panel").style.display = "flex";
                return;
            }

            await loadConversations();
            ensureConversationSidebarRendered();
            connectWebSocket();
        })();
    