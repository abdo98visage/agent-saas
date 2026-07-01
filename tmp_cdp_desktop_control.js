const wsUrl = process.argv[2];

if (!wsUrl) {
  throw new Error("Usage: node tmp_cdp_desktop_control.js <webSocketDebuggerUrl>");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

class CdpClient {
  constructor(url) {
    this.url = url;
    this.socket = null;
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
    const message = { id, method, params };
    this.socket.send(JSON.stringify(message));
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

async function waitFor(label, fn, timeoutMs = 120000, intervalMs = 1000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const value = await fn();
    if (value) {
      return value;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for ${label}`);
}

function snapshotExpression() {
  return `(() => {
    const messages = Array.from(document.querySelectorAll('#chat-body .message')).map((node) => ({
      role: ['user', 'assistant', 'system'].find((name) => node.classList.contains(name)) || 'unknown',
      text: (node.innerText || '').trim(),
    }));
    return {
      readyState: document.readyState,
      title: (document.getElementById('chat-title')?.innerText || '').trim(),
      employee: (document.getElementById('employee-name')?.innerText || '').trim(),
      profile: (document.getElementById('profile-badge')?.innerText || '').trim(),
      activationVisible: getComputedStyle(document.getElementById('activation-panel')).display !== 'none',
      currentProjectPath: (document.getElementById('context-panel-subtitle')?.innerText || '').trim(),
      queueBadge: (document.getElementById('queue-badge')?.innerText || '').trim(),
      messages,
    };
  })()`;
}

async function main() {
  const client = new CdpClient(wsUrl);
  await client.connect();
  await client.send("Page.enable");
  await client.send("Runtime.enable");

  const session = await waitFor("desktop session", async () => {
    const snapshot = await client.evaluate(snapshotExpression());
    if (!snapshot || snapshot.readyState !== "complete") {
      return null;
    }
    if (snapshot.activationVisible) {
      throw new Error("Activation panel is visible.");
    }
    if (!snapshot.employee || snapshot.employee.includes("Unknown")) {
      return null;
    }
    return snapshot;
  });

  console.log("Desktop session:");
  console.log(JSON.stringify(session, null, 2));

  await client.evaluate(`(() => { document.getElementById('sidebar-new-chat')?.click(); return true; })()`);
  await sleep(1500);

  const assistantCount = () => client.evaluate(
    `(() => Array.from(document.querySelectorAll('#chat-body .message.assistant')).filter((node) => (node.innerText || '').trim()).length)()`,
  );

  async function sendPrompt(text) {
    const before = await assistantCount();
    await client.evaluate(`(() => {
      const input = document.getElementById('message-input');
      input.value = ${JSON.stringify(text)};
      input.dispatchEvent(new Event('input', { bubbles: true }));
      document.getElementById('btn-send')?.click();
      return true;
    })()`);

    const snapshot = await waitFor("assistant reply", async () => {
      const current = await client.evaluate(snapshotExpression());
      const lastSystem = current.messages.filter((item) => item.role === 'system').at(-1)?.text || '';
      const currentAssistantCount = current.messages.filter((item) => item.role === 'assistant' && item.text).length;
      if (lastSystem.includes('تم حفظ الرسالة')) {
        throw new Error(`Message was queued locally: ${lastSystem}`);
      }
      if (lastSystem.startsWith('خطأ:')) {
        throw new Error(lastSystem);
      }
      if (currentAssistantCount > before) {
        return current;
      }
      return null;
    });

    return snapshot.messages.filter((item) => item.role === "assistant").at(-1)?.text || "";
  }

  const prompt1 = "مرحبا. اذكر اسم الموظف الحالي والبروفايل الحالي في سطر واحد فقط.";
  console.log(`Sending prompt 1: ${prompt1}`);
  const reply1 = await sendPrompt(prompt1);
  console.log("Assistant reply 1:");
  console.log(reply1);

  const prompt2 = "ما الملفات الموجودة في المجلد المفتوح الآن؟ اذكر أسماء الملفات فقط بشكل مختصر.";
  console.log(`Sending prompt 2: ${prompt2}`);
  const reply2 = await sendPrompt(prompt2);
  console.log("Assistant reply 2:");
  console.log(reply2);
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
