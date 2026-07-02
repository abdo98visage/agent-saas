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
            fallbackWorkspacePath: "",
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
            messageApprovalGranted: false,
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
            state.settings.projectOutputFilesMap = state.settings.projectOutputFilesMap && typeof state.settings.projectOutputFilesMap === "object"
                ? state.settings.projectOutputFilesMap
                : {};
            state.settings.conversationTitleMap = state.settings.conversationTitleMap && typeof state.settings.conversationTitleMap === "object"
                ? state.settings.conversationTitleMap
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
                els.employeeMeta.textContent = metaParts.join(" • ") || fallbackMeta;
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
            const optionsHtml = [`<option value="">${getLocale() === "en" ? "Default assigned profile" : "الملف الافتراضي المخصص"}</option>`]
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
            state.messageApprovalGranted = false;
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
            document.getElementById("act-status").innerHTML = `<span class="text-danger">${escapeHtml(message || "انتهت الجلسة الحالية. فعّل الحساب أو سجّل الدخول من جديد.")}</span>`;
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
                ? `يوجد ${queue.length} رسالة بانتظار عودة الاتصال.`
                : "لا توجد رسائل معلقة.";
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
                    appendSystemMessage(`تعذر إرسال رسالة معلقة: ${error.message}`);
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
            const defaultWorkspace = window.electronAPI.getDefaultWorkspaceRoot
                ? await window.electronAPI.getDefaultWorkspaceRoot()
                : null;
            state.fallbackWorkspacePath = defaultWorkspace && !defaultWorkspace.error
                ? defaultWorkspace.path || ""
                : "";
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
            } catch (error) {
                console.error("Failed to load conversations:", error);
                state.conversations = [];
                renderConversations();
            }
        }

        function getSettingsPanelOpen() {
            return els.settingsPanel.style.display !== "none";
        }

        function toggleSettingsPanel(forceState) {
            const shouldOpen = typeof forceState === "boolean" ? forceState : !getSettingsPanelOpen();
            els.settingsPanel.style.display = shouldOpen ? "block" : "none";
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
