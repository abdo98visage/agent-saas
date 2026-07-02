        function renderConversations() {
            els.conversationsList.innerHTML = state.conversations.map((conversation) => `
                <div class="conversation-item ${state.currentConversation === conversation.conversation_id ? "active" : ""}" data-id="${conversation.conversation_id}">
                    <div class="text-truncate">${conversation.title || "محادثة"}</div>
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
                <button class="btn btn-sm btn-primary-custom sidebar-action-btn" id="sidebar-new-chat" type="button">
                    + ${t("newChat")}
                </button>
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-chats-section" type="button">
                        <span>${t("chats")}</span>
                        <span class="collapse-arrow">${state.settings.chatsCollapsed ? "▸" : "▾"}</span>
                    </button>
                </div>
                ${state.settings.chatsCollapsed ? "" : `
                    <div class="sidebar-group">
                        ${visibleGeneralSessions.map((conversation) => renderConversationButton(conversation)).join("")}
                        ${generalSessions.length === 0 ? `<div class="sidebar-empty">${t("welcomeBody")}</div>` : ""}
                        ${generalSessions.length > MAX_VISIBLE_GENERAL_SESSIONS ? `
                            <button class="show-more-btn" id="btn-toggle-all-chats" type="button">
                                ${state.settings.showAllChats ? t("showLess") : t("showMore")}
                            </button>
                        ` : ""}
                    </div>
                `}
                <div class="section-divider"></div>
                <div class="section-toggle-row">
                    <button class="section-toggle-btn" id="toggle-projects-section" type="button">
                        <span>${t("projects")}</span>
                        <span class="collapse-arrow">${state.settings.projectsCollapsed ? "▸" : "▾"}</span>
                    </button>
                    <button class="section-add-btn" id="btn-add-project" type="button" title="${t("openDirectory")}">
                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                            <path d="M3 7.5C3 6.12 4.12 5 5.5 5H9L11 7H18.5C19.88 7 21 8.12 21 9.5V16.5C21 17.88 19.88 19 18.5 19H5.5C4.12 19 3 17.88 3 16.5V7.5Z" fill="currentColor"></path>
                        </svg>
                        <span>${t("addProject")}</span>
                    </button>
                </div>
                ${state.settings.projectsCollapsed ? "" : `<div class="sidebar-group">${projectsHtml}</div>`}
            `;            document.getElementById("sidebar-new-chat")?.addEventListener("click", () => {
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
            els.chatTitle.textContent = "محادثة جديدة";
            resetStreamingState();
            renderConversations();
        }

        function renderConversationButton(conversation, className = "general-session-item") {
            const activeClass = state.currentConversation === conversation.conversation_id ? "active" : "";
            const title = typeof getConversationDisplayTitle === "function"
                ? getConversationDisplayTitle(conversation)
                : (conversation.title || t("newChat"));
            return `
                <button class="${className} ${activeClass}" data-conversation-id="${conversation.conversation_id}" type="button">
                    <div class="text-truncate">${escapeHtml(title)}</div>
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
                        <div class="project-item project-item-static">
                            <div class="project-card project-card-static ${state.currentProjectId === project.id ? "project-card-current" : ""}">
                                <div class="project-card-head">
                                    <button class="project-action-btn compact project-inline-add" data-project-session="${project.id}" type="button" title="${t("projectNewSession")}">
                                        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                                            <path d="M12 5V19M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path>
                                        </svg>
                                    </button>
                                    <button class="project-title-stack ${state.currentProjectId === project.id ? "active" : ""}" data-project-id="${project.id}" type="button">
                                        <div class="project-name text-truncate">${escapeHtml(project.name)}</div>
                                        <span class="project-path">${escapeHtml(project.path)}</span>
                                    </button>
                                    <button class="project-inline-chevron" data-project-toggle="${project.id}" type="button" title="${project.expanded ? t("hideSessions") : t("showSessions")}">
                                        <span class="collapse-arrow">${renderChevron(project.expanded)}</span>
                                    </button>
                                </div>
                            ${project.expanded ? `
                                <div class="project-sessions project-sessions-embedded">
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
                <div class="section-toggle-row sidebar-section-row">
                    <button class="section-toggle-btn sidebar-section-btn" id="toggle-chats-section" type="button">
                        <span class="sidebar-section-title-wrap">
                            <span class="sidebar-section-title">${t("chats")}</span>
                            <span class="sidebar-section-icon" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M7 8.5C7 6.57 8.57 5 10.5 5H15.5C17.43 5 19 6.57 19 8.5C19 10.43 17.43 12 15.5 12H13.7L11 14.2V12H10.5C8.57 12 7 10.43 7 8.5Z" fill="currentColor" opacity="0.35"></path>
                                    <circle cx="11" cy="8.5" r="0.9" fill="currentColor"></circle>
                                    <circle cx="13" cy="8.5" r="0.9" fill="currentColor"></circle>
                                    <circle cx="15" cy="8.5" r="0.9" fill="currentColor"></circle>
                                </svg>
                            </span>
                        </span>
                        <span class="sidebar-section-actions">
                            <span class="sidebar-mini-pill" data-sidebar-action="new-chat">${t("sectionNew")}</span>
                            <span class="collapse-arrow sidebar-leading-arrow">${renderChevron(!state.settings.chatsCollapsed)}</span>
                        </span>
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
                <div class="section-toggle-row sidebar-section-row">
                    <button class="section-toggle-btn sidebar-section-btn" id="toggle-projects-section" type="button">
                        <span class="sidebar-section-title-wrap">
                            <span class="sidebar-section-title">${t("projects")}</span>
                            <span class="sidebar-section-icon sidebar-section-icon-folder" aria-hidden="true">
                                <svg viewBox="0 0 24 24" fill="none">
                                    <path d="M4 8.2C4 6.98 4.98 6 6.2 6H9.2L10.7 7.5H17.8C19.02 7.5 20 8.48 20 9.7V15.8C20 17.02 19.02 18 17.8 18H6.2C4.98 18 4 17.02 4 15.8V8.2Z" fill="currentColor"></path>
                                </svg>
                            </span>
                        </span>
                        <span class="sidebar-section-actions">
                            <span class="sidebar-mini-pill" data-sidebar-action="new-project">${t("sectionNew")}</span>
                            <span class="collapse-arrow sidebar-leading-arrow">${renderChevron(!state.settings.projectsCollapsed)}</span>
                        </span>
                    </button>
                </div>
                ${state.settings.projectsCollapsed ? "" : `<div class="sidebar-group">${projectsHtml}</div>`}
            `;

            document.getElementById("toggle-chats-section")?.addEventListener("click", (event) => {
                if (event.target?.closest?.('[data-sidebar-action="new-chat"]')) {
                    newConversation();
                    return;
                }
                void toggleChatsCollapsed();
            });
            document.getElementById("toggle-projects-section")?.addEventListener("click", (event) => {
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
            els.chatTitle.textContent = getCurrentProject()?.name || "محادثة مشروع";
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
            const confirmed = window.confirm(`حذف المشروع ${project.name} من قائمة الديسكتوب؟ لن يتم حذف ملفات المجلد.`);
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
            const confirmed = window.confirm(`هل أنت متأكد من حذف المشروع ${project.name} من قائمة البرنامج؟ لن يتم حذف أي ملف من جهاز الكمبيوتر.`);
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
            updateComposerStatus(`تم فتح المشروع: ${project.name}`);
        }

        async function getWebSocketToken() {
            try {
                const data = await apiRequest("/auth/ws-token", { method: "POST" });
                state.authRequired = false;
                return data.access_token || state.settings.token;
            } catch (error) {
                if (/Invalid or expired token|Token has been revoked|Missing auth token|inactive/i.test(error.message || "")) {
                    await handleAuthFailure("الجلسة منتهية أو غير صالحة. أعد التفعيل أو حدّث رمز الدخول أولاً.");
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

            const apiUrl = new URL(state.settings.apiUrl || "http://localhost:8001/api");
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
                    void handleAuthFailure("فشل اتصال الديسكتوب لأن جلسة الدخول لم تعد صالحة.");
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
            const effectiveWorkspacePath = getEffectiveWorkspacePath();
            return {
                root_name: effectiveWorkspacePath ? effectiveWorkspacePath.split(/[\\/]/).pop() : "",
                root_path: effectiveWorkspacePath,
                selected_files: Array.from(state.selectedProjectFiles),
                file_paths: state.projectFiles.map((file) => file.path).slice(0, 200),
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
            const workspacePath = getEffectiveWorkspacePath();
            if (!workspacePath) {
                await sendToolResult(data.request_id, data.tool, false, null, "No local workspace is selected in the desktop app.");
                return;
            }

            try {
                let result;
                switch (data.tool) {
                    case "list_files":
                        result = await window.electronAPI.listFiles(workspacePath, data.args || {});
                        break;
                    case "search_files":
                        result = await window.electronAPI.searchFiles(
                            workspacePath,
                            (data.args && data.args.query) || "",
                            (data.args && data.args.limit) || 20,
                        );
                        break;
                    case "read_file":
                        result = await window.electronAPI.readFile(workspacePath, data.args && data.args.path);
                        break;
                    case "read_multiple_files":
                        result = await window.electronAPI.readMultipleFiles(
                            workspacePath,
                            (data.args && data.args.paths) || [],
                        );
                        break;
                    default:
                        throw new Error(`Unsupported local tool: ${data.tool}`);
                }

                if (result && result.error) {
                    await sendToolResult(data.request_id, data.tool, false, null, result.error);
                    appendSystemMessage(`فشل تنفيذ ${data.tool}: ${result.error}`);
                    return;
                }

                await sendToolResult(data.request_id, data.tool, true, result, "");
            } catch (error) {
                await sendToolResult(data.request_id, data.tool, false, null, error.message);
                appendSystemMessage(`فشل تنفيذ ${data.tool}: ${error.message}`);
            }
        }

        async function executeApplyRequest(data) {
            const workspacePath = getEffectiveWorkspacePath();
            if (!workspacePath) {
                await sendApplyResult(data.request_id, false, null, "No local workspace is selected in the desktop app.");
                return;
            }

            try {
                const preview = await window.electronAPI.prepareWorkspaceChanges(workspacePath, data.changes || []);
                if (preview.error) {
                    await sendApplyResult(data.request_id, false, null, preview.error);
                    appendSystemMessage(`تعذر تجهيز التعديلات: ${preview.error}`);
                    return;
                }

                const summary = data.summary || "Hermes proposed workspace changes.";
                const requireApproval = Boolean(data.require_approval) && !state.messageApprovalGranted;
                if (requireApproval) {
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
                        appendSystemMessage("تم رفض التعديلات المحلية المقترحة.");
                        return;
                    }
                    state.messageApprovalGranted = true;
                }

                const applied = await window.electronAPI.applyWorkspaceChanges(preview.previewToken);
                if (applied.error) {
                    await sendApplyResult(data.request_id, false, null, applied.error);
                    appendSystemMessage(`فشل تطبيق التعديلات: ${applied.error}`);
                    return;
                }

                await refreshProjectFiles();
                await sendApplyResult(data.request_id, true, {
                    approved: true,
                    changed_files: applied.changedFiles || [],
                    summary,
                }, "");
                if (requireApproval) {
                    appendSystemMessage("تم تطبيق التعديلات المحلية بعد الموافقة.");
                }
            } catch (error) {
                await sendApplyResult(data.request_id, false, null, error.message);
                appendSystemMessage(`فشل تطبيق التعديلات: ${error.message}`);
            }
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
                    if (data.request_id && !state.messageApprovalGranted) {
                        appendSystemMessage(data.summary || data.title || "Hermes requested approval for local changes.");
                    }
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
                els.contextStatus.textContent = "لا يوجد مجلد مشروع محدد.";
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
                ? `تم إرفاق ${result.files.length} ملف/مقطع مناسب مع الرسالة.`
                : "لم يتم العثور على مقاطع مناسبة من المشروع.";
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

        async function waitForWebSocketOpen(timeoutMs = 15000) {
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

