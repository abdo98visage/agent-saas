#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const apiUrlIndex = process.argv.indexOf("--api-url");
const apiUrl = apiUrlIndex >= 0 ? process.argv[apiUrlIndex + 1] : "http://localhost:8002";
const durationIndex = process.argv.indexOf("--duration-minutes");
const durationMinutes = durationIndex >= 0 ? Number(process.argv[durationIndex + 1]) : 150;
const intervalIndex = process.argv.indexOf("--interval-seconds");
const intervalSeconds = intervalIndex >= 0 ? Number(process.argv[intervalIndex + 1]) : 180;
const evidenceIndex = process.argv.indexOf("--evidence");
const evidencePath = path.resolve(evidenceIndex >= 0 ? process.argv[evidenceIndex + 1] : "uat-evidence/live-desktop-uat.jsonl");
const authRegressionOnly = process.argv.includes("--auth-regression-only");
const faultProbeIndex = process.argv.indexOf("--fault-probe-marker");
const faultProbeMarker = faultProbeIndex >= 0 ? process.argv[faultProbeIndex + 1] : "";
const faultProbePromptIndex = process.argv.indexOf("--fault-probe-prompt");
const faultProbePrompt = faultProbePromptIndex >= 0
  ? process.argv[faultProbePromptIndex + 1]
  : `Reply exactly ${faultProbeMarker}.`;
const faultProbeRejectIndex = process.argv.indexOf("--fault-probe-reject-marker");
const faultProbeRejectMarker = faultProbeRejectIndex >= 0 ? process.argv[faultProbeRejectIndex + 1] : "";
const faultUserIndex = process.argv.indexOf("--fault-user");
const faultUser = faultUserIndex >= 0 ? process.argv[faultUserIndex + 1] : "hr";
const faultProbeAcceptError = process.argv.includes("--fault-probe-accept-error");
const faultInspectOnly = process.argv.includes("--fault-inspect-only");
const networkCutMarkerIndex = process.argv.indexOf("--resilience-marker");
const networkCutMarker = networkCutMarkerIndex >= 0 ? process.argv[networkCutMarkerIndex + 1] : "";
const networkCutPhaseIndex = process.argv.indexOf("--resilience-phase");
const networkCutPhase = networkCutPhaseIndex >= 0 ? process.argv[networkCutPhaseIndex + 1] : "start";
const skipQuotaSetup = process.argv.includes("--skip-quota-setup");
const desktopOnly = process.argv.includes("--desktop-only");
const newConversations = process.argv.includes("--new-conversations");
const sessionExpiryUat = process.argv.includes("--session-expiry-uat");
const allowDirectDesktop = process.argv.includes("--allow-direct-desktop");
const portBaseIndex = process.argv.indexOf("--port-base");
const portBase = portBaseIndex >= 0 ? Number(process.argv[portBaseIndex + 1]) : 9341;
const users = [
  { label: "accounting", port: portBase },
  { label: "marketing", port: portBase + 1 },
  { label: "hr", port: portBase + 2 },
  { label: "it", port: portBase + 3 },
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function record(event) {
  const row = { at: new Date().toISOString(), ...event };
  fs.mkdirSync(path.dirname(evidencePath), { recursive: true });
  fs.appendFileSync(evidencePath, `${JSON.stringify(row)}\n`, "utf8");
  console.log(JSON.stringify(row));
}

async function waitFor(fn, timeoutMs, label) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const result = await fn();
      if (result) return result;
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }
  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("CDP connect timeout")), 10000);
      this.ws.addEventListener("open", () => { clearTimeout(timeout); resolve(); }, { once: true });
      this.ws.addEventListener("error", () => { clearTimeout(timeout); reject(new Error("CDP connect error")); }, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timeout);
      if (message.error) pending.reject(new Error(message.error.message));
      else pending.resolve(message.result);
    });
    const rejectPending = (reason) => {
      for (const [id, pending] of this.pending) {
        this.pending.delete(id);
        clearTimeout(pending.timeout);
        pending.reject(new Error(`CDP connection closed: ${reason}`));
      }
    };
    this.ws.addEventListener("close", (event) => rejectPending(`code=${event.code}`));
    this.ws.addEventListener("error", () => rejectPending("websocket error"));
  }
  send(method, params = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error(`CDP connection is not open for ${method}`));
    }
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP command timeout: ${method}`));
      }, 120000);
      this.pending.set(id, { resolve, reject, timeout });
    });
  }
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "Runtime.evaluate failed");
    return result.result.value;
  }
  close() { this.ws?.close(); }
}

async function connectDesktop(user) {
  const page = await waitFor(async () => {
    const response = await fetch(`http://127.0.0.1:${user.port}/json/list`);
    if (!response.ok) return null;
    return (await response.json()).find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  }, 300000, `${user.label} Desktop debugger`);
  const cdp = new CdpClient(page.webSocketDebuggerUrl);
  await cdp.connect();
  await cdp.send("Runtime.enable");
  const holdReady = (sessionExpiryUat || allowDirectDesktop) ? "true" : "window.__desktopE2eHold === true";
  const readyExpression = faultInspectOnly
    ? `typeof state !== 'undefined' && ${holdReady} && Boolean(state.settings.token)`
    : `typeof state !== 'undefined' && ${holdReady} && Boolean(state.settings.token) && state.ws?.readyState === WebSocket.OPEN && !state.isStreaming`;
  await waitFor(
    () => cdp.evaluate(readyExpression),
    300000,
    `${user.label} Desktop ready`,
  );
  const identity = await cdp.evaluate("({user: state.currentUser, profileName: state.settings.profileName, token: state.settings.token, conversationId: state.currentConversation})");
  return { ...user, cdp, ...identity };
}

async function apiRequest(method, apiPath, body, token, extraHeaders = {}) {
  const response = await fetch(`${apiUrl}${apiPath}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extraHeaders,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(`${method} ${apiPath} returned ${response.status}: ${text}`);
  return data;
}

async function prepareLongRunQuotas(adminToken, clients) {
  const keyResponse = await apiRequest("GET", "/api/admin/api-keys", undefined, adminToken);
  const userIds = new Set(clients.map((client) => client.user.id));
  const profileIds = new Set(clients.map((client) => client.assignedProfile.id));
  await Promise.all(clients.flatMap((client) => [
    apiRequest("PUT", `/api/admin/employees/${client.user.id}/quotas`, {
      max_tokens_per_day: 1_000_000_000,
      max_requests_per_day: 100_000,
    }, adminToken),
    apiRequest("PUT", `/api/admin/profiles/${client.assignedProfile.id}`, {
      max_tokens_per_day: 1_000_000_000,
      max_requests_per_day: 100_000,
    }, adminToken),
  ]));
  const scopedKeys = keyResponse.api_keys.filter((key) => (
    userIds.has(key.user_id)
    || (key.profile_ids || []).some((profileId) => profileIds.has(profileId))
  ));
  await Promise.all(scopedKeys.map((key) => apiRequest(
    "PUT",
    `/api/admin/api-keys/${key.id}`,
    { daily_budget: 1_000_000_000 },
    adminToken,
  )));
  for (const client of clients) {
    await client.cdp.evaluate("flushQueuedMessages()");
    await waitFor(
      () => client.cdp.evaluate("state.settings.offlineQueue.length === 0 && !state.isStreaming"),
      180000,
      `${client.label} pre-existing queue flush`,
    );
  }
  record({ type: "quota_setup_pass", users: clients.length, api_keys: scopedKeys.length });
}

async function sendChat(client, prompt, expected, label = "periodic", rejected = "") {
  const before = await client.cdp.evaluate("state.currentMessages.length");
  const started = Date.now();
  await client.cdp.evaluate(`(async()=>{document.getElementById("message-input").value=${JSON.stringify(prompt)};await sendMessage();})()`);
  const content = await waitFor(
    () => client.cdp.evaluate(`(()=>{const last=state.currentMessages[state.currentMessages.length-1];return !state.isStreaming&&state.currentMessages.length>${before + 1}&&last?.role==="assistant"?last.content:""})()`),
    120000,
    `${client.label} ${label} response`,
  );
  if (expected && !content.includes(expected)) throw new Error(`${client.label} expected ${expected}, got ${content}`);
  if (rejected && content.includes(rejected)) throw new Error(`${client.label} returned prohibited marker ${rejected}`);
  const result = { user: client.label, step: label, latency_ms: Date.now() - started, content: content.slice(0, 160) };
  record({ type: "chat_pass", ...result });
  return result;
}

async function addAccountingKnowledge(adminToken, accounting) {
  const code = `LIVE-ACCT-KNOWLEDGE-${Date.now()}`;
  const slug = `live-uat-${Date.now()}`;
  const source = await apiRequest("POST", "/api/admin/knowledge/sources", {
    name: "Live UAT Accounting Update",
    slug,
    source_type: "managed_upload",
    classification: "internal",
    allowed_user_ids: [accounting.user.id],
  }, adminToken);
  await apiRequest("POST", `/api/admin/knowledge/sources/${source.id}/documents`, {
    replace_all: true,
    documents: [{ external_id: "live-update", title: "Live update", content: `The current live accounting update code is ${code}.`, metadata: { uat: true } }],
  }, adminToken);
  await sendChat(accounting, "Using enterprise knowledge only, what is the current live accounting update code?", code, "admin knowledge update");
  return source.id;
}

async function revokeItMcp(adminToken, itClient) {
  const profile = itClient.assignedProfile || (await apiRequest("GET", "/api/auth/assigned-profiles", undefined, itClient.token)).profiles.find((item) => item.name === itClient.profileName);
  const bindings = await apiRequest("GET", `/api/admin/mcp/profiles/${profile.id}/bindings`, undefined, adminToken);
  for (const binding of bindings.bindings.filter((item) => item.is_active)) {
    await apiRequest("DELETE", `/api/admin/mcp/profiles/${profile.id}/bindings/${binding.server_id}`, undefined, adminToken);
  }
  await itClient.cdp.evaluate("loadAvailableMcpServers()");
  await waitFor(() => itClient.cdp.evaluate("state.availableMcpServers.length === 0"), 30000, "IT MCP revoke visibility");
  record({ type: "admin_change_pass", step: "IT MCP revoked while Desktop remained open", user: "it" });
}

async function offlineQueueRoundtrip(hr) {
  const marker = `OFFLINE-ONCE-${Date.now()}`;
  await hr.cdp.evaluate(`(async()=>{window.__uatApiUrl=state.settings.apiUrl;if(state.ws){state.ws.onclose=null;state.ws.close();state.ws=null;}state.settings.apiUrl="http://127.0.0.1:1/api";await window.electronAPI.setSettings(state.settings);document.getElementById("message-input").value=${JSON.stringify(`Reply exactly ${marker}.`)};await sendMessage();})()`);
  await waitFor(() => hr.cdp.evaluate("state.settings.offlineQueue.length === 1"), 15000, "HR offline queue item");
  await sleep(120000);
  await hr.cdp.evaluate("(async()=>{state.settings.apiUrl=window.__uatApiUrl;await window.electronAPI.setSettings(state.settings);connectWebSocket();})()");
  await waitFor(() => hr.cdp.evaluate("state.ws?.readyState === WebSocket.OPEN"), 30000, "HR reconnect");
  await waitFor(() => hr.cdp.evaluate("state.settings.offlineQueue.length === 0 && !state.isStreaming"), 120000, "HR queue flush");
  const conversationId = await hr.cdp.evaluate("state.currentConversation");
  const history = await apiRequest("GET", `/api/chat/conversations/${conversationId}/messages?limit=200`, undefined, hr.token);
  const count = history.messages.filter((item) => item.role === "user" && item.content === `Reply exactly ${marker}.`).length;
  if (count !== 1) throw new Error(`HR offline message persisted ${count} times`);
  record({ type: "offline_queue_pass", user: "hr", marker, persisted_count: count });
}

async function reloadMarketing(marketing) {
  const conversationId = await marketing.cdp.evaluate("state.currentConversation");
  await marketing.cdp.send("Page.reload", { ignoreCache: true });
  await waitFor(() => marketing.cdp.evaluate("typeof state !== 'undefined' && Boolean(state.settings.token) && state.ws?.readyState === WebSocket.OPEN"), 60000, "Marketing Desktop reload");
  await marketing.cdp.evaluate(`loadConversation(${JSON.stringify(conversationId)})`);
  await waitFor(() => marketing.cdp.evaluate(`state.currentConversation === ${JSON.stringify(conversationId)} && state.currentMessages.length > 0`), 30000, "Marketing conversation restore");
  await sendChat(marketing, "After reopening, reply exactly REOPENED-OK.", "REOPENED-OK", "Desktop reopen continuity");
}

async function disableAndRestoreHr(adminToken, hr) {
  await apiRequest("PUT", `/api/admin/employees/${hr.user.id}`, { is_active: false }, adminToken);
  await hr.cdp.evaluate(`(()=>{document.getElementById("message-input").value="Reply exactly SHOULD-NOT-RUN.";void sendMessage();})()`);
  await waitFor(() => hr.cdp.evaluate("state.authRequired === true"), 30000, "disabled HR authentication rejection");
  const queuedAfterRejection = await hr.cdp.evaluate("state.settings.offlineQueue.length");
  if (queuedAfterRejection !== 0) throw new Error(`Disabled HR message remained queued (${queuedAfterRejection})`);
  record({ type: "expected_rejection", user: "hr", detail: "Authentication revoked; rejected message was not queued" });
  await apiRequest("PUT", `/api/admin/employees/${hr.user.id}`, { is_active: true }, adminToken);
  const login = await apiRequest(
    "POST",
    "/api/auth/login",
    { email: hr.user.email, password: "Employee123" },
    undefined,
    { "X-Client-Type": "desktop" },
  );
  hr.token = login.access_token;
  await hr.cdp.evaluate(`(async()=>{state.settings.token=${JSON.stringify(login.access_token)};state.settings.refreshToken=${JSON.stringify(login.refresh_token || "")};await window.electronAPI.setSettings(state.settings);state.authRequired=false;connectWebSocket();})()`);
  await waitFor(() => hr.cdp.evaluate("state.ws?.readyState === WebSocket.OPEN"), 30000, "HR login after re-enable");
  await sendChat(hr, "Reply exactly REACTIVATED-OK.", "REACTIVATED-OK", "re-enabled user");
  const conversationId = await hr.cdp.evaluate("state.currentConversation");
  const history = await apiRequest("GET", `/api/chat/conversations/${conversationId}/messages?limit=200`, undefined, hr.token);
  if (history.messages.some((item) => item.content.includes("SHOULD-NOT-RUN"))) {
    throw new Error("Message rejected while disabled executed after reactivation");
  }
}

function tokenExpiry(token) {
  const payload = JSON.parse(Buffer.from(String(token).split(".")[1], "base64url").toString("utf8"));
  return Number(payload.exp || 0);
}

async function sessionExpiryRound(clients) {
  const byLabel = Object.fromEntries(clients.map((item) => [item.label, item]));

  const primed = await Promise.all(clients.map(async (client) => {
    const previous = await client.cdp.evaluate("state.settings.token");
    const token = await client.cdp.evaluate("refreshAccessToken()");
    if (!token || token === previous) throw new Error(`${client.label} did not rotate onto a short access token`);
    client.expiredToken = token;
    return { user: client.label, expires_at: tokenExpiry(token) };
  }));
  record({ type: "session_short_tokens_primed", tokens: primed });

  const expiry = Math.max(...primed.map((item) => item.expires_at));
  while (Math.floor(Date.now() / 1000) <= expiry + 1) {
    const remaining = expiry + 2 - Math.floor(Date.now() / 1000);
    if (remaining > 0 && remaining % 30 === 0) record({ type: "session_expiry_wait", remaining_seconds: remaining });
    await sleep(1000);
  }
  record({ type: "session_access_tokens_naturally_expired", expired_at: expiry });

  const accountingBefore = await byLabel.accounting.cdp.evaluate("state.settings.token");
  const accountingMe = await byLabel.accounting.cdp.evaluate("apiRequest('/auth/me')");
  const accountingAfter = await byLabel.accounting.cdp.evaluate("state.settings.token");
  if (!accountingMe?.id || accountingAfter === accountingBefore) throw new Error("REST 401 did not rotate Accounting access token");
  record({ type: "session_rest_refresh_pass", user: "accounting", employee_id: accountingMe.id });

  const marketingBefore = await byLabel.marketing.cdp.evaluate("state.settings.token");
  const concurrent = await byLabel.marketing.cdp.evaluate("Promise.all([apiRequest('/auth/me'),apiRequest('/auth/assigned-profiles')])");
  const marketingAfter = await byLabel.marketing.cdp.evaluate("state.settings.token");
  if (!concurrent?.[0]?.id || !Array.isArray(concurrent?.[1]?.profiles) || marketingAfter === marketingBefore) {
    throw new Error("Concurrent 401 refresh did not complete safely");
  }
  record({ type: "session_concurrent_401_pass", user: "marketing", requests: 2 });

  const hrBefore = await byLabel.hr.cdp.evaluate("state.settings.token");
  await byLabel.hr.cdp.evaluate("(()=>{if(state.ws){state.ws.onclose=null;state.ws.close();state.ws=null;}return connectWebSocket();})()");
  await waitFor(() => byLabel.hr.cdp.evaluate("state.ws?.readyState === WebSocket.OPEN"), 30000, "HR WebSocket refresh reconnect");
  const hrAfter = await byLabel.hr.cdp.evaluate("state.settings.token");
  if (hrAfter === hrBefore) throw new Error("WebSocket reopen did not refresh the expired HR access token");
  record({ type: "session_websocket_refresh_pass", user: "hr" });

  const itBefore = await byLabel.it.cdp.evaluate("state.settings.token");
  await byLabel.it.cdp.send("Page.reload", { ignoreCache: true });
  await waitFor(
    () => byLabel.it.cdp.evaluate("typeof state !== 'undefined' && !state.authRequired && state.ws?.readyState === WebSocket.OPEN && Boolean(state.currentUser)"),
    60000,
    "IT Desktop reopen after access expiry",
  );
  const itAfter = await byLabel.it.cdp.evaluate("state.settings.token");
  if (itAfter === itBefore) throw new Error("Desktop reopen did not refresh the expired IT access token");
  record({ type: "session_desktop_reopen_pass", user: "it" });

  const rotationExpiries = [];
  for (let index = 0; index < 3; index += 1) {
    await sleep(1100);
    const token = await byLabel.accounting.cdp.evaluate("refreshAccessToken()");
    rotationExpiries.push(tokenExpiry(token));
  }
  if (new Set(rotationExpiries).size !== rotationExpiries.length) throw new Error("Repeated refresh rotations returned duplicate access tokens");
  record({ type: "session_repeated_rotation_pass", user: "accounting", rotations: 3, expiries: rotationExpiries });

  const freshAdmin = await apiRequest("POST", "/api/auth/login", { email: "admin@company.com", password: "admin123" });
  const invite = await apiRequest(
    "POST",
    `/api/admin/employees/${byLabel.hr.user.id}/desktop-invite`,
    undefined,
    freshAdmin.access_token,
  );
  await byLabel.hr.cdp.evaluate("state.ws?.send(JSON.stringify({type:'heartbeat'}))");
  await waitFor(() => byLabel.hr.cdp.evaluate("state.authRequired === true"), 30000, "HR administrative session revocation");

  const unaffected = await Promise.all(["accounting", "marketing", "it"].map(async (label) => ({
    user: label,
    me: await byLabel[label].cdp.evaluate("apiRequest('/auth/me')"),
    ws: await byLabel[label].cdp.evaluate("state.ws?.readyState"),
  })));
  if (unaffected.some((item) => !item.me?.id || item.ws !== 1)) throw new Error("Administrative revocation affected another Desktop user");
  record({ type: "session_admin_revoke_pass", user: "hr", unaffected_users: unaffected.map((item) => item.user) });

  const activationResponse = await fetch(`${apiUrl}/api/auth/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Client-Type": "desktop" },
    body: JSON.stringify({ token: invite.invite_token, password: "Employee123" }),
  });
  const activation = await activationResponse.json();
  if (!activationResponse.ok || !activation.access_token || !activation.refresh_token) {
    throw new Error(`HR reactivation failed: ${JSON.stringify(activation)}`);
  }
  byLabel.hr.token = activation.access_token;
  await byLabel.hr.cdp.evaluate(`(async()=>{
    state.settings=await window.electronAPI.setSettings({...state.settings,token:${JSON.stringify(activation.access_token)},refreshToken:${JSON.stringify(activation.refresh_token)}});
    state.authRequired=false;
    document.getElementById("activation-panel").style.display="none";
    await loadCurrentUser();
    await connectWebSocket();
  })()`);
  await waitFor(() => byLabel.hr.cdp.evaluate("!state.authRequired && state.ws?.readyState === WebSocket.OPEN && Boolean(state.currentUser)"), 30000, "HR reactivation");
  record({ type: "session_reactivation_pass", user: "hr" });

  record({ type: "uat_complete", status: "passed", scenario: "access expiry and refresh rotation" });
}

async function main() {
  if (!Number.isFinite(durationMinutes) || durationMinutes <= 0) throw new Error("Invalid duration");
  fs.rmSync(evidencePath, { force: true });
  const admin = desktopOnly
    ? null
    : await apiRequest("POST", "/api/auth/login", { email: "admin@company.com", password: "admin123" });
  const selectedUsers = (authRegressionOnly || faultProbeMarker || faultInspectOnly || networkCutMarker)
    ? users.filter((item) => item.label === (authRegressionOnly ? "hr" : faultUser))
    : users;
  const clients = await Promise.all(selectedUsers.map(connectDesktop));
  for (const client of clients) {
    if (!client.user) {
      client.user = await apiRequest("GET", "/api/auth/me", undefined, client.token);
    }
    if (!desktopOnly && !sessionExpiryUat) {
      const assigned = await apiRequest("GET", "/api/auth/assigned-profiles", undefined, client.token);
      client.assignedProfile = assigned.profiles.find((item) => item.name === client.profileName);
    }
    record({ type: "desktop_ready", user: client.label, employee_id: client.user.id, profile: client.profileName, port: client.port });
  }
  if (faultInspectOnly) {
    try {
      await clients[0].cdp.evaluate("loadAvailableMcpServers()");
      const stateSnapshot = await clients[0].cdp.evaluate(`(()=>{
        const last=state.currentMessages[state.currentMessages.length-1];
        const systems=[...document.querySelectorAll(".message.system")].slice(-5).map((item)=>item.textContent.trim());
        return {
          queue:state.settings.offlineQueue.length,
          authRequired:state.authRequired,
          isStreaming:state.isStreaming,
          wsReadyState:state.ws?.readyState??-1,
          queueRetryAttempt:state.queueRetryAttempt,
          queueRetryScheduled:Boolean(state.queueRetryTimer),
          queueFlushInProgress:state.queueFlushInProgress,
          lastRole:last?.role||"",
          lastContent:last?.content||"",
          availableMcpServers:(state.availableMcpServers||[]).map((server)=>({slug:server.slug,status:server.connection?.status||""})),
          mcpEvents:(window.__mcpE2eEvents||[]).slice(-10),
          systems,
        };
      })()`);
      record({ type: "fault_inspection", user: clients[0].label, ...stateSnapshot });
      record({ type: "uat_complete", status: "passed", scenario: "fault inspection" });
    } finally {
      clients.forEach((client) => client.cdp.close());
    }
    return;
  }
  if (!skipQuotaSetup && admin) {
    await prepareLongRunQuotas(admin.access_token, clients);
  }
  if (newConversations) {
    await Promise.all(clients.map((client) => client.cdp.evaluate("newConversation()")));
  }
  const byLabel = Object.fromEntries(clients.map((item) => [item.label, item]));
  if (networkCutMarker) {
    try {
      if (!['start', 'done'].includes(networkCutPhase)) throw new Error(`Unknown network cut phase: ${networkCutPhase}`);
      const faultClient = byLabel[faultUser];
      if (!faultClient) throw new Error(`Unknown fault user: ${faultUser}`);
      const before = await faultClient.cdp.evaluate("state.currentMessages.length");
      await faultClient.cdp.evaluate(`(()=>{
        const original=state.ws.onmessage;
        let cut=false;
        state.ws.onmessage=(event)=>{
          let message=null;
          try{message=JSON.parse(event.data);}catch{}
          original.call(state.ws,event);
          if(!cut&&message?.type===${JSON.stringify(networkCutPhase)}){
            cut=true;
            setTimeout(()=>state.ws?.close(),0);
          }
        };
        document.getElementById("message-input").value=${JSON.stringify(`Reply exactly ${networkCutMarker}.`)};
        void sendMessage();
      })()`);
      const outcome = await waitFor(() => faultClient.cdp.evaluate(`(()=>{
        const last=state.currentMessages[state.currentMessages.length-1];
        return state.ws?.readyState===WebSocket.OPEN
          && state.settings.offlineQueue.length===0
          && !state.isStreaming
          && state.currentMessages.length>${before + 1}
          && last?.role==="assistant"
          && last.content.includes(${JSON.stringify(networkCutMarker)})
          ? {queue:0,lastContent:last.content,conversationId:state.currentConversation}
          : null;
      })()`), 180000, `network cut after ${networkCutPhase}`);
      const history = await apiRequest("GET", `/api/chat/conversations/${outcome.conversationId}/messages?limit=200`, undefined, faultClient.token);
      const exactPrompt = `Reply exactly ${networkCutMarker}.`;
      const userCount = history.messages.filter((item) => item.role === "user" && item.content === exactPrompt).length;
      const assistantCount = history.messages.filter((item) => item.role === "assistant" && item.content.includes(networkCutMarker)).length;
      if (userCount !== 1 || assistantCount !== 1) throw new Error(`Network cut persisted user=${userCount}, assistant=${assistantCount}`);
      record({type:"network_cut_pass",phase:networkCutPhase,user:faultUser,marker:networkCutMarker,user_count:userCount,assistant_count:assistantCount,...outcome});
      record({type:"uat_complete",status:"passed",scenario:`network cut after ${networkCutPhase}`});
    } finally {
      clients.forEach((client) => client.cdp.close());
    }
    return;
  }
  if (faultProbeMarker) {
    try {
      const faultClient = byLabel[faultUser];
      if (!faultClient) throw new Error(`Unknown fault user: ${faultUser}`);
      if (faultProbeAcceptError) {
        const before = await faultClient.cdp.evaluate("state.currentMessages.length");
        await faultClient.cdp.evaluate(`(()=>{document.getElementById("message-input").value=${JSON.stringify(faultProbePrompt)};void sendMessage();})()`);
        record({ type: "fault_dispatched", user: faultUser, marker: faultProbeMarker });
        const outcome = await waitFor(() => faultClient.cdp.evaluate(`(()=>{
          const last=state.currentMessages[state.currentMessages.length-1];
          const systems=[...document.querySelectorAll(".message.system")].slice(-3).map((item)=>item.textContent.trim());
          if(state.isStreaming) return null;
          if(state.settings.offlineQueue.length===0 && state.currentMessages.length<=${before + 1}) return null;
          return {queue:state.settings.offlineQueue.length,authRequired:state.authRequired,lastRole:last?.role||"",lastContent:last?.content||"",systems};
        })()`), 180000, "fault outcome");
        record({ type: "fault_observation", user: faultUser, marker: faultProbeMarker, ...outcome });
      } else {
        await sendChat(faultClient, faultProbePrompt, faultProbeMarker, "fault recovery probe", faultProbeRejectMarker);
      }
      record({ type: "uat_complete", status: "passed", scenario: "fault probe", marker: faultProbeMarker });
    } finally {
      clients.forEach((client) => client.cdp.close());
    }
    return;
  }
  if (authRegressionOnly) {
    try {
      await disableAndRestoreHr(admin.access_token, byLabel.hr);
      record({ type: "uat_complete", status: "passed", scenario: "auth queue boundary" });
    } finally {
      clients.forEach((client) => client.cdp.close());
    }
    return;
  }
  if (sessionExpiryUat) {
    try {
      await sessionExpiryRound(clients);
    } finally {
      clients.forEach((client) => client.cdp.close());
    }
    return;
  }
  const started = Date.now();
  const deadline = started + durationMinutes * 60000;
  let cycle = 0;
  let knowledgeDone = false;
  let temporaryKnowledgeSourceId = null;
  let continuityDone = false;
  let adminDisableDone = false;
  const latencies = Object.fromEntries(users.map((item) => [item.label, []]));
  try {
    while (Date.now() < deadline) {
      cycle += 1;
      const cycleStart = Date.now();
      const elapsedMinutes = (cycleStart - started) / 60000;
      const replies = await Promise.all(clients.map((client) => sendChat(
        client,
        `Live UAT cycle ${cycle} for ${client.label}. Reply exactly LIVE-${client.label.toUpperCase()}-${cycle}.`,
        `LIVE-${client.label.toUpperCase()}-${cycle}`,
        `cycle ${cycle}`,
      )));
      for (const reply of replies) latencies[reply.user].push(reply.latency_ms);
      record({ type: "cycle_pass", cycle, elapsed_minutes: Number(elapsedMinutes.toFixed(2)) });
      if (!knowledgeDone && elapsedMinutes >= 60) {
        temporaryKnowledgeSourceId = await addAccountingKnowledge(admin.access_token, byLabel.accounting);
        await revokeItMcp(admin.access_token, byLabel.it);
        knowledgeDone = true;
      }
      if (!continuityDone && elapsedMinutes >= 90) {
        await Promise.all([offlineQueueRoundtrip(byLabel.hr), reloadMarketing(byLabel.marketing)]);
        continuityDone = true;
      }
      if (!adminDisableDone && elapsedMinutes >= 120) {
        await disableAndRestoreHr(admin.access_token, byLabel.hr);
        adminDisableDone = true;
      }
      const remaining = intervalSeconds * 1000 - (Date.now() - cycleStart);
      if (remaining > 0 && Date.now() + remaining < deadline) await sleep(remaining);
    }
    const summary = {};
    for (const [label, values] of Object.entries(latencies)) {
      const sorted = [...values].sort((a, b) => a - b);
      summary[label] = {
        requests: values.length,
        p50_ms: sorted[Math.floor(sorted.length * 0.5)] || 0,
        p95_ms: sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))] || 0,
        max_ms: sorted.at(-1) || 0,
      };
    }
    record({ type: "uat_complete", status: "passed", duration_minutes: durationMinutes, cycles: cycle, latency: summary });
  } finally {
    if (temporaryKnowledgeSourceId) {
      try {
        const cleanupAdmin = await apiRequest("POST", "/api/auth/login", {
          email: "admin@company.com",
          password: "admin123",
        });
        await apiRequest(
          "DELETE",
          `/api/admin/knowledge/sources/${temporaryKnowledgeSourceId}`,
          undefined,
          cleanupAdmin.access_token,
        );
        record({ type: "cleanup_pass", resource: "temporary knowledge source", id: temporaryKnowledgeSourceId });
      } catch (error) {
        record({ type: "cleanup_failed", resource: "temporary knowledge source", error: error.message });
      }
    }
    clients.forEach((client) => client.cdp.close());
  }
}

main().catch((error) => {
  record({ type: "uat_complete", status: "failed", error: error.stack || error.message });
  process.exit(1);
});
