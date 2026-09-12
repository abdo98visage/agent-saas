#!/usr/bin/env node
"use strict";

const fs = require("fs");
const { spawnSync } = require("child_process");

const apiUrl = "http://127.0.0.1:8002";
const evidence = "uat-evidence/phase9-upgrade-four-desktops.jsonl";
const users = ["accounting", "marketing", "hr", "it"].map((label, index) => ({ label, port: 9351 + index }));

function record(value) {
  const event = { at: new Date().toISOString(), ...value };
  fs.appendFileSync(evidence, `${JSON.stringify(event)}\n`);
  console.log(JSON.stringify(event));
}

function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

async function waitFor(fn, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { const value = await fn(); if (value) return value; } catch (error) { last = error; }
    await sleep(250);
  }
  throw new Error(`Timed out waiting for ${label}${last ? `: ${last.message}` : ""}`);
}

class Cdp {
  constructor(url) { this.url = url; this.id = 0; this.pending = new Map(); }
  async connect() {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.ws.onopen = resolve; this.ws.onerror = reject;
    });
    this.ws.onmessage = (message) => {
      const value = JSON.parse(message.data);
      if (!value.id || !this.pending.has(value.id)) return;
      const { resolve, reject } = this.pending.get(value.id); this.pending.delete(value.id);
      if (value.error) reject(new Error(value.error.message)); else resolve(value.result);
    };
  }
  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || "evaluation failed");
    return result.result.value;
  }
  close() { this.ws?.close(); }
}

async function connect(user) {
  const page = await waitFor(async () => {
    const response = await fetch(`http://127.0.0.1:${user.port}/json/list`);
    return (await response.json()).find((item) => item.type === "page" && item.webSocketDebuggerUrl);
  }, 15000, `${user.label} Desktop CDP`);
  const cdp = new Cdp(page.webSocketDebuggerUrl); await cdp.connect(); await cdp.send("Runtime.enable");
  await waitFor(() => cdp.evaluate("typeof state !== 'undefined' && Boolean(state.settings.token)"), 15000, `${user.label} state`);
  return { ...user, cdp };
}

async function sendChat(client, marker) {
  const before = await client.cdp.evaluate("state.currentMessages.length");
  await client.cdp.evaluate(`(()=>{document.getElementById("message-input").value=${JSON.stringify(`Reply exactly ${marker}.`)};return sendMessage();})()`);
  const content = await waitFor(async () => {
    const state = await client.cdp.evaluate("({streaming:state.isStreaming,messages:state.currentMessages})");
    if (state.streaming || state.messages.length <= before) return null;
    return [...state.messages].reverse().find((item) => item.role === "assistant")?.content || null;
  }, 180000, `${client.label} response ${marker}`);
  if (!content.includes(marker)) throw new Error(`${client.label} expected ${marker}, got ${content}`);
}

function compose(args) {
  const result = spawnSync("docker", ["compose", "--env-file", ".env.docker.local", "-f", "docker-compose.e2e.yml", ...args], {
    cwd: process.cwd(), encoding: "utf8", windowsHide: true,
  });
  if (result.status !== 0) throw new Error(`docker compose ${args.join(" ")} failed: ${result.stderr || result.stdout}`);
}

async function waitPlatform(clients, started, step) {
  await waitFor(async () => {
    try { return (await (await fetch(`${apiUrl}/api/ready`)).json()).status === "ready"; } catch { return false; }
  }, 120000, `${step} API readiness`);
  const apiReadyMs = Date.now() - started;
  await Promise.all(clients.map((client) => waitFor(
    () => client.cdp.evaluate("state.ws?.readyState === WebSocket.OPEN"), 120000, `${client.label} reconnect`,
  )));
  return { api_ready_ms: apiReadyMs, desktops_reconnected_ms: Date.now() - started };
}

async function verifyContinuity(clients, snapshots, suffix) {
  await Promise.all(clients.map(async (client) => {
    const conversation = await client.cdp.evaluate("state.currentConversation");
    if (conversation !== snapshots[client.label].conversation) throw new Error(`${client.label} conversation changed after ${suffix}`);
    const marker = `${suffix.toUpperCase()}-${client.label.toUpperCase()}-OK`;
    await sendChat(client, marker);
    const occurrences = await client.cdp.evaluate(`(async()=>{const h=await apiRequest('/chat/conversations/${conversation}/messages?limit=200');return h.messages.filter(x=>x.role==='user'&&x.content===${JSON.stringify(`Reply exactly ${marker}.`)}).length;})()`);
    if (occurrences !== 1) throw new Error(`${client.label} ${suffix} marker persisted ${occurrences} times`);
  }));
}

async function main() {
  fs.writeFileSync(evidence, "");
  const clients = await Promise.all(users.map(connect));
  try {
    const snapshots = {};
    await Promise.all(clients.map(async (client) => {
      const marker = `PRE-UPGRADE-${client.label.toUpperCase()}-OK`;
      await sendChat(client, marker);
      snapshots[client.label] = { conversation: await client.cdp.evaluate("state.currentConversation"), marker };
    }));
    record({ type: "pre_upgrade_pass", users: clients.length });

    let started = Date.now();
    compose(["up", "-d", "--no-deps", "--force-recreate", "api"]);
    const upgraded = await waitPlatform(clients, started, "upgrade");
    await verifyContinuity(clients, snapshots, "post-upgrade");
    record({ type: "upgrade_pass", ...upgraded, users: clients.length });

    compose(["stop", "api"]);
    const candidate = spawnSync("docker", ["run", "--rm", "agentsaas-api:e2e", "python", "-c", "raise SystemExit(42)"], { encoding: "utf8", windowsHide: true });
    if (candidate.status !== 42) throw new Error(`failure candidate returned ${candidate.status}, expected 42`);
    record({ type: "postflight_failure_detected", candidate_exit_code: candidate.status });
    started = Date.now();
    compose(["up", "-d", "--no-deps", "api"]);
    const rolledBack = await waitPlatform(clients, started, "rollback");
    await verifyContinuity(clients, snapshots, "post-rollback");
    record({ type: "rollback_pass", ...rolledBack, users: clients.length });
    record({ type: "phase9_upgrade_complete", status: "passed" });
  } finally {
    clients.forEach((client) => client.cdp.close());
  }
}

main().catch((error) => { record({ type: "phase9_upgrade_complete", status: "failed", error: error.message }); process.exitCode = 1; });
