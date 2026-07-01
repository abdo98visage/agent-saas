const wsUrl = process.argv[2];
const prompt = process.argv.slice(3).join(" ");

if (!wsUrl || !prompt) {
  throw new Error("Usage: node tmp_cdp_send_and_wait.js <webSocketDebuggerUrl> <prompt>");
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

  const before = await client.evaluate(
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
      messages: Array.from(document.querySelectorAll('#chat-body .message')).map((node) => ({
        role: ['user', 'assistant', 'system'].find((name) => node.classList.contains(name)) || 'unknown',
        text: (node.innerText || '').trim(),
      })),
    }))()`);
    const lastSystem = snapshot.messages.filter((item) => item.role === "system").at(-1)?.text || "";
    const assistants = snapshot.messages.filter((item) => item.role === "assistant" && item.text);
    if (lastSystem.includes("تم حفظ الرسالة")) {
      throw new Error(lastSystem);
    }
    if (lastSystem.startsWith("خطأ:")) {
      throw new Error(lastSystem);
    }
    if (assistants.length > before) {
      console.log(JSON.stringify({
        prompt,
        reply: assistants.at(-1)?.text || "",
        messages: snapshot.messages,
      }, null, 2));
      return;
    }
    await sleep(1000);
  }

  throw new Error("Timed out waiting for assistant reply.");
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
