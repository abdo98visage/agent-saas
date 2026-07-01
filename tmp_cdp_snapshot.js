const wsUrl = process.argv[2];

if (!wsUrl) {
  throw new Error("Usage: node tmp_cdp_snapshot.js <webSocketDebuggerUrl>");
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

(async () => {
  const client = new Client(wsUrl);
  await client.connect();
  await client.send("Runtime.enable");
  const snapshot = await client.evaluate(`(() => ({
    title: document.title,
    employee: document.getElementById('employee-name')?.innerText || '',
    profile: document.getElementById('profile-badge')?.innerText || '',
    messages: Array.from(document.querySelectorAll('#chat-body .message')).map((node) => ({
      className: node.className,
      text: node.innerText || '',
    })),
  }))()`);
  console.log(JSON.stringify(snapshot, null, 2));
})().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
