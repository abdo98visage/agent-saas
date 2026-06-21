#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

function parseArgs() {
  const args = {
    apiUrl: "http://localhost:8002",
    exePath: path.resolve("desktop", "dist", "win-unpacked", "FQ-SaaS Workspace.exe"),
    adminEmail: "admin@company.com",
    adminPassword: "admin123",
    employeePassword: "Employee123",
    provider: "minimax",
    model: "Qwen3.6-27B-IQ4_XS.gguf",
    port: 9333,
  };
  for (let index = 2; index < process.argv.length; index += 1) {
    const arg = process.argv[index];
    const next = process.argv[index + 1];
    if (arg === "--api-url") args.apiUrl = next, index += 1;
    else if (arg === "--exe-path") args.exePath = path.resolve(next), index += 1;
    else if (arg === "--admin-email") args.adminEmail = next, index += 1;
    else if (arg === "--admin-password") args.adminPassword = next, index += 1;
    else if (arg === "--employee-password") args.employeePassword = next, index += 1;
    else if (arg === "--provider") args.provider = next, index += 1;
    else if (arg === "--model") args.model = next, index += 1;
    else if (arg === "--port") args.port = Number(next), index += 1;
  }
  return args;
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function apiRequest(baseUrl, method, apiPath, body, token) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(`${baseUrl}${apiPath}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(`${method} ${apiPath} returned ${response.status}: ${text}`);
  }
  return data;
}

async function waitFor(fn, timeoutMs, label) {
  const started = Date.now();
  let lastError;
  while (Date.now() - started < timeoutMs) {
    try {
      const result = await fn();
      if (result) {
        return result;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
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
      const timer = setTimeout(() => reject(new Error("CDP WebSocket open timed out")), 10000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener("error", (event) => {
        clearTimeout(timer);
        reject(new Error(`CDP WebSocket error: ${event.message || "unknown"}`));
      }, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !this.pending.has(message.id)) {
        return;
      }
      const { resolve, reject } = this.pending.get(message.id);
      this.pending.delete(message.id);
      if (message.error) {
        reject(new Error(message.error.message || JSON.stringify(message.error)));
      } else {
        resolve(message.result);
      }
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.ws.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP command timed out: ${method}`));
        }
      }, 30000);
    });
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error(result.exceptionDetails.text || "Runtime.evaluate failed");
    }
    return result.result.value;
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

async function waitForDebugger(port) {
  const listUrl = `http://127.0.0.1:${port}/json/list`;
  return waitFor(async () => {
    const response = await fetch(listUrl);
    if (!response.ok) {
      return null;
    }
    const pages = await response.json();
    return pages.find((page) => page.type === "page" && page.webSocketDebuggerUrl);
  }, 30000, "Electron debugger page");
}

async function createDesktopEmployee(args) {
  const suffix = crypto.randomBytes(5).toString("hex");
  const adminLogin = await apiRequest(args.apiUrl, "POST", "/api/auth/login", {
    email: args.adminEmail,
    password: args.adminPassword,
  });
  const adminToken = adminLogin.access_token;
  await apiRequest(args.apiUrl, "PUT", "/api/admin/agent-templates/default", {
    model_name: args.model,
    max_tokens_per_request: 256,
    temperature: 0.1,
    system_prompt: "Reply with a short direct final answer.",
  }, adminToken);
  const profileName = `Desktop Hermes ${suffix}`;
  const profileSlug = `desktop-hermes-${suffix}`;
  const employeeEmail = `desktop-${suffix}@example.com`;

  const profile = await apiRequest(args.apiUrl, "POST", "/api/admin/profiles", {
    name: profileName,
    slug: profileSlug,
    runtime_type: "hermes",
    agents_md: "# Desktop E2E\nValidate packaged desktop execution.",
    soul_md: "Reliable desktop QA assistant.",
    skills: ["desktop", "qa"],
    system_prompt: "Respond briefly for packaged desktop validation.",
    max_tokens_per_day: 100000,
    max_requests_per_day: 1000,
    daily_cost_budget: 100000,
    allowed_providers: [args.provider],
    allowed_tools: ["local_runtime"],
    allowed_mcp_servers: [],
  }, adminToken);

  await apiRequest(args.apiUrl, "POST", "/api/admin/api-keys", {
    owner_type: "profile",
    profile_id: profile.id,
    provider: args.provider,
    api_key: "sk-desktop-e2e-profile-key",
    daily_budget: 100000,
  }, adminToken);

  const employee = await apiRequest(args.apiUrl, "POST", "/api/admin/employees", {
    email: employeeEmail,
    full_name: "Desktop E2E Employee",
    department: "qa",
    role: "employee",
    max_tokens_per_day: 100000,
    max_requests_per_day: 1000,
  }, adminToken);

  await apiRequest(args.apiUrl, "POST", "/api/admin/assignments", {
    user_id: employee.id,
    profile_id: profile.id,
    priority: 0,
  }, adminToken);

  return {
    adminToken,
    profileName,
    profileSlug,
    employeeEmail,
    employeeId: employee.id,
    inviteToken: employee.invite_token,
  };
}

function jsString(value) {
  return JSON.stringify(value);
}

async function main() {
  const args = parseArgs();
  assert(fs.existsSync(args.exePath), `Desktop EXE not found: ${args.exePath}`);

  const employee = await createDesktopEmployee(args);
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "agentsaas-desktop-user-"));
  const workspaceDir = fs.mkdtempSync(path.join(os.tmpdir(), "agentsaas-desktop-workspace-"));
  fs.mkdirSync(path.join(workspaceDir, "src"), { recursive: true });
  fs.writeFileSync(path.join(workspaceDir, "src", "campaign.js"), "export const headline = 'old headline';\n", "utf-8");
  fs.writeFileSync(path.join(workspaceDir, "README.md"), "# Desktop E2E\nCampaign validation notes.\n", "utf-8");
  fs.writeFileSync(path.join(workspaceDir, ".env.local"), "SECRET=should-not-be-scanned\n", "utf-8");

  const desktopApiUrl = `${args.apiUrl.replace(/\/$/, "")}/api`;
  const child = spawn(args.exePath, [
    `--remote-debugging-port=${args.port}`,
    `--user-data-dir=${userDataDir}`,
  ], {
    env: { ...process.env, API_URL: desktopApiUrl },
    stdio: "ignore",
    windowsHide: true,
  });

  let cdp;
  try {
    const page = await waitForDebugger(args.port);
    cdp = new CdpClient(page.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.send("Runtime.enable");

    await waitFor(
      () => cdp.evaluate("Boolean(window.electronAPI && document.getElementById('activation-panel'))"),
      15000,
      "desktop renderer preload",
    );

    await cdp.evaluate(`
      (async () => {
        const settings = await window.electronAPI.getSettings();
        if (settings.token) {
          state.settings = await window.electronAPI.setSettings({
            ...settings,
            token: "",
            offlineQueue: [],
            selectedProjectFiles: [],
          });
        }
        document.getElementById("act-api-url").value = ${jsString(desktopApiUrl)};
        document.getElementById("activation-panel").style.display = "flex";
      })()
    `);
    await waitFor(
      () => cdp.evaluate("getComputedStyle(document.getElementById('activation-panel')).display !== 'none'"),
      10000,
      "desktop activation panel",
    );
    const activationVisible = await cdp.evaluate("getComputedStyle(document.getElementById('activation-panel')).display !== 'none'");
    assert(activationVisible, "Activation panel was not visible for fresh desktop profile");

    await cdp.evaluate(`
      (() => {
        document.getElementById("act-api-url").value = ${jsString(desktopApiUrl)};
        document.getElementById("act-token").value = ${jsString(employee.inviteToken)};
        document.getElementById("act-password").value = ${jsString(args.employeePassword)};
        document.getElementById("btn-activate").click();
      })()
    `);

    await waitFor(
      () => cdp.evaluate("document.getElementById('activation-panel').style.display === 'none'"),
      15000,
      "desktop activation",
    );
    await waitFor(
      () => cdp.evaluate("Boolean(state.settings.token && state.ws && state.ws.readyState === WebSocket.OPEN)"),
      15000,
      "desktop WebSocket connection",
    );

    await cdp.evaluate(`
      (async () => {
        document.getElementById("message-input").value = "Write one short packaged desktop E2E response.";
        await sendMessage();
      })()
    `);
    await waitFor(
      () => cdp.evaluate(`
        (() => {
          const last = state.currentMessages[state.currentMessages.length - 1];
          return Boolean(last && last.role === "user" && last.content.includes("packaged desktop E2E response"));
        })()
      `),
      10000,
      "desktop user message dispatch",
    );
    const assistantContent = await waitFor(
      () => cdp.evaluate(`
        (() => {
          const last = state.currentMessages[state.currentMessages.length - 1];
          if (!state.isStreaming && last && last.role === "assistant" && last.content.trim().length > 0) {
            return last.content;
          }
          const rendered = [...document.querySelectorAll(".message.assistant")].at(-1);
          return !state.isStreaming && rendered && rendered.textContent.trim().length > 0 ? rendered.textContent : "";
        })()
      `),
      60000,
      "desktop WebSocket chat response",
    );
    assert(assistantContent.trim().length > 0, "Desktop chat did not render Hermes response");

    const projectResult = await cdp.evaluate(`
      (async () => {
        const root = ${jsString(workspaceDir)};
        const scan = await window.electronAPI.scanFolder(root);
        const read = await window.electronAPI.readFile(root, "src\\\\campaign.js");
        const context = await window.electronAPI.buildProjectContext(root, "campaign headline", ["src\\\\campaign.js"]);
        const preview = await window.electronAPI.prepareFileWrite(root, "src\\\\campaign.js", "export const headline = 'new desktop headline';\\n");
        const applied = await window.electronAPI.applyFileWrite(preview.previewToken);
        const updateStatus = await window.electronAPI.getUpdateStatus();
        const checkedUpdate = await window.electronAPI.checkForUpdates();
        const settings = await window.electronAPI.setSettings({
          ...(await window.electronAPI.getSettings()),
          offlineQueue: [{ id: "desktop-e2e", content: "queued", createdAt: new Date().toISOString() }],
        });
        return { scan, read, context, preview, applied, updateStatus, checkedUpdate, settings };
      })()
    `);
    assert(projectResult.scan.count >= 2, "Desktop scanFolder did not find expected text files");
    assert(!projectResult.scan.files.some((file) => file.path.includes(".env")), "Desktop scanFolder included .env file");
    assert(projectResult.read.content.includes("old headline"), "Desktop readFile did not read selected file");
    assert(projectResult.context.context.includes("campaign.js"), "Desktop buildProjectContext missed selected file");
    assert(projectResult.preview.previewToken, "Desktop prepareFileWrite did not return preview token");
    assert(projectResult.applied.ok, "Desktop applyFileWrite did not apply preview");
    assert(fs.readFileSync(path.join(workspaceDir, "src", "campaign.js"), "utf-8").includes("new desktop headline"), "Desktop file write did not persist");
    assert(projectResult.updateStatus.configured === false, "Desktop update status should be not configured in local test");
    assert(projectResult.checkedUpdate.state === "not_configured", "Desktop checkForUpdates did not report not_configured");
    assert(projectResult.settings.offlineQueue.length === 1, "Desktop offline queue settings did not persist");

    await cdp.evaluate("document.getElementById('settings-panel').style.display = 'block'");
    await cdp.evaluate("document.getElementById('btn-tg-gen-code').click()");
    const bindCode = await waitFor(
      () => cdp.evaluate("document.getElementById('tg-bind-code').value"),
      15000,
      "desktop Telegram bind code",
    );
    assert(bindCode.length >= 6, "Desktop Telegram bind code was not generated");
    const chatId = 910000000 + Number.parseInt(crypto.randomBytes(2).toString("hex"), 16);
    await apiRequest(args.apiUrl, "POST", "/api/telegram/webhook", {
      message: { chat: { id: chatId }, text: `/bind ${bindCode}` },
    });
    await cdp.evaluate("document.getElementById('btn-tg-bind').click()");
    const telegramStatus = await waitFor(
      () => cdp.evaluate("document.getElementById('tg-bind-status').textContent"),
      15000,
      "desktop Telegram bind confirmation",
    );
    assert(!/خطأ|error/i.test(telegramStatus), `Desktop Telegram bind failed: ${telegramStatus}`);

    const conversations = await apiRequest(args.apiUrl, "GET", "/api/chat/conversations", undefined, await cdp.evaluate("state.settings.token"));
    assert(conversations.count >= 1, "Desktop chat did not create a persisted conversation");

    console.log("PASS desktop packaged EXE activation");
    console.log("PASS desktop WebSocket chat");
    console.log("PASS desktop project scan/context/read/preview/apply write");
    console.log("PASS desktop Telegram bind UI flow");
    console.log("PASS desktop offline queue and update status");
    console.log(`PROFILE ${employee.profileSlug}`);
    console.log(`EMPLOYEE ${employee.employeeEmail}`);
  } finally {
    if (cdp) {
      try {
        await cdp.send("Browser.close");
      } catch (_) {
        cdp.close();
      }
    }
    if (!child.killed) {
      child.kill();
    }
    fs.rmSync(userDataDir, { recursive: true, force: true });
    fs.rmSync(workspaceDir, { recursive: true, force: true });
  }
}

main().catch((error) => {
  console.error(`FAIL desktop packaged EXE test: ${error.stack || error.message}`);
  process.exit(1);
});
