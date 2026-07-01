const fs = require("fs");

const wsUrl = process.argv[2];
const filePath = process.argv[3];
const prompt = process.argv.slice(4).join(" ");

if (!wsUrl || !filePath || !prompt) {
  throw new Error("Usage: node tmp_cdp_approval_test.js <wsUrl> <filePath> <prompt>");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class Client {
  constructor(url) {
    this.url = url;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.socket = new WebSocket(this.url);
    await new Promise((resolve, reject) => {
      this.socket.addEventListener("open", resolve, { once: true });
      this.socket.addEventListener("error", reject, { once: true });
    });
    this.socket.addEventListener("message", (event) => {
      const payload = JSON.parse(String(event.data));
      if (!payload.id) {
        return;
      }
      const pending = this.pending.get(payload.id);
      if (!pending) {
        return;
      }
      this.pending.delete(payload.id);
      if (payload.error) {
        pending.reject(new Error(payload.error.message || "CDP error"));
        return;
      }
      pending.resolve(payload.result);
    });
  }

  send(method, params = {}) {
    const id = this.nextId++;
    this.socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });
  }

  async evaluate(expression) {
    const result = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    return result.result?.value;
  }
}

async function main() {
  const client = new Client(wsUrl);
  await client.connect();
  await client.send("Runtime.enable");

  await client.evaluate(`(() => {
    window.__confirmCalls = [];
    const originalConfirm = window.confirm.bind(window);
    window.confirm = (message) => {
      window.__confirmCalls.push(String(message || ""));
      return true;
    };
    const approval = document.getElementById('composer-approval-select');
    if (approval) {
      approval.value = 'approve_for_me';
      approval.dispatchEvent(new Event('change', { bubbles: true }));
    }
    document.getElementById('sidebar-new-chat')?.click();
    return true;
  })()`);

  await sleep(1500);

  const beforeAssistantCount = await client.evaluate(
    `(() => Array.from(document.querySelectorAll('#chat-body .message.assistant')).filter((node) => (node.innerText || '').trim()).length)()`,
  );

  await client.evaluate(`(() => {
    const input = document.getElementById('message-input');
    input.value = ${JSON.stringify(prompt)};
    input.dispatchEvent(new Event('input', { bubbles: true }));
    document.getElementById('btn-send')?.click();
    return true;
  })()`);

  const start = Date.now();
  while (Date.now() - start < 120000) {
    const snapshot = await client.evaluate(`(() => ({
      confirmCalls: window.__confirmCalls || [],
      approvalMode: document.getElementById('composer-approval-select')?.value || '',
      messages: Array.from(document.querySelectorAll('#chat-body .message')).map((node) => ({
        role: ['user', 'assistant', 'system'].find((name) => node.classList.contains(name)) || 'unknown',
        text: (node.innerText || '').trim(),
      })),
    }))()`);
    const assistantCount = snapshot.messages.filter((item) => item.role === "assistant" && item.text).length;
    const systemLast = snapshot.messages.filter((item) => item.role === "system").at(-1)?.text || "";
    const fileContent = fs.readFileSync(filePath, "utf8");
    const markerCount = (fileContent.match(/ZXCV_APPROVAL_MARKER/g) || []).length;

    if (assistantCount > beforeAssistantCount || systemLast.startsWith("خطأ:")) {
      console.log(JSON.stringify({
        approvalMode: snapshot.approvalMode,
        confirmCalls: snapshot.confirmCalls,
        markerCount,
        fileContent,
        messages: snapshot.messages,
      }, null, 2));
      return;
    }

    if (markerCount > 1 || snapshot.confirmCalls.length > 0) {
      console.log(JSON.stringify({
        approvalMode: snapshot.approvalMode,
        confirmCalls: snapshot.confirmCalls,
        markerCount,
        fileContent,
        messages: snapshot.messages,
        earlyStop: true,
      }, null, 2));
      return;
    }

    await sleep(1000);
  }

  const fileContent = fs.readFileSync(filePath, "utf8");
  console.log(JSON.stringify({
    timeout: true,
    fileContent,
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
