#!/usr/bin/env node
"use strict";

const { spawn } = require("child_process");
const path = require("path");

const baseUrlIndex = process.argv.indexOf("--api-url");
const baseUrl = baseUrlIndex >= 0 ? process.argv[baseUrlIndex + 1] : "http://localhost:8002";
const holdIndex = process.argv.indexOf("--hold-open-seconds");
const holdOpenSeconds = holdIndex >= 0 ? Number(process.argv[holdIndex + 1]) : 60;
const runner = path.resolve(__dirname, "desktop_e2e_test.js");
const users = [
  { label: "accounting", port: 9341, canary: "ALPHA-ACCT-731" },
  { label: "marketing", port: 9342, canary: "BETA-MKT-842" },
  { label: "hr", port: 9343, canary: "GAMMA-HR-953" },
  { label: "it", port: 9344, canary: "DELTA-IT-164", mcpServerSlug: "context7-durable-0241f5" },
];

function runUser(user) {
  return new Promise((resolve) => {
    const childArgs = [
      runner,
      "--api-url", baseUrl,
      "--provider", "openai",
      "--port", String(user.port),
      "--visible",
      "--hold-open-seconds", String(holdOpenSeconds),
      "--role-label", user.label,
      "--knowledge-canary", user.canary,
      "--forbid-canaries", users.filter((item) => item !== user).map((item) => item.canary).join(","),
    ];
    if (user.mcpServerSlug) {
      childArgs.push("--mcp-server-slug", user.mcpServerSlug, "--provision-mcp");
    }
    const child = spawn(process.execPath, childArgs, {
      cwd: path.resolve(__dirname, ".."),
      windowsHide: false,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk;
      process.stdout.write(`[${user.label}] ${chunk}`);
    });
    child.stderr.on("data", (chunk) => {
      output += chunk;
      process.stderr.write(`[${user.label}] ${chunk}`);
    });
    child.on("exit", (code) => resolve({ ...user, code, output }));
  });
}

async function main() {
  console.log(`Starting ${users.length} independent packaged Desktop users against ${baseUrl}`);
  const results = await Promise.all(users.map(runUser));
  const failed = results.filter((result) => result.code !== 0);
  console.log(JSON.stringify({
    status: failed.length ? "failed" : "passed",
    users: results.map(({ label, port, code, output }) => ({
      label,
      port,
      code,
      profile: output.match(/^PROFILE (.+)$/m)?.[1] || null,
      employee: output.match(/^EMPLOYEE (.+)$/m)?.[1] || null,
    })),
  }));
  if (failed.length) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
