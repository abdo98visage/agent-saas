const path = require("path");
const { app, BrowserWindow } = require("electron");

require(path.join(__dirname, "desktop", "src", "main", "main.js"));

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitFor(getValue, { timeoutMs = 60000, intervalMs = 500, label = "condition" } = {}) {
  const start = Date.now();
  let lastError = null;
  while (Date.now() - start < timeoutMs) {
    try {
      const value = await getValue();
      if (value) {
        return value;
      }
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for ${label}${lastError ? `: ${lastError.message}` : ""}`);
}

async function evalInRenderer(win, source) {
  return win.webContents.executeJavaScript(source, true);
}

async function getUiSnapshot(win) {
  return evalInRenderer(
    win,
    `(() => {
      const messages = Array.from(document.querySelectorAll("#chat-body .message")).map((node) => ({
        role: ["user", "assistant", "system"].find((name) => node.classList.contains(name)) || "unknown",
        text: (node.innerText || "").trim(),
      }));
      return {
        title: (document.getElementById("chat-title")?.innerText || "").trim(),
        employee: (document.getElementById("employee-name")?.innerText || "").trim(),
        profile: (document.getElementById("profile-badge")?.innerText || "").trim(),
        activationVisible: getComputedStyle(document.getElementById("activation-panel")).display !== "none",
        queueBadge: (document.getElementById("queue-badge")?.innerText || "").trim(),
        messageCount: messages.length,
        messages,
      };
    })()`,
  );
}

async function startFreshConversation(win) {
  await evalInRenderer(
    win,
    `(() => {
      document.getElementById("sidebar-new-chat")?.click();
      return true;
    })()`,
  );
  await sleep(1000);
}

async function sendChatMessage(win, text) {
  await evalInRenderer(
    win,
    `(() => {
      const input = document.getElementById("message-input");
      input.value = ${JSON.stringify(text)};
      input.dispatchEvent(new Event("input", { bubbles: true }));
      document.getElementById("btn-send")?.click();
      return true;
    })()`,
  );
}

async function waitForAgentTurn(win, previousAssistantCount) {
  return waitFor(
    async () => {
      const snapshot = await getUiSnapshot(win);
      const assistantMessages = snapshot.messages.filter((item) => item.role === "assistant" && item.text);
      const systemMessages = snapshot.messages.filter((item) => item.role === "system" && item.text);
      const latestSystem = systemMessages.at(-1)?.text || "";
      if (latestSystem.includes("تم حفظ الرسالة")) {
        throw new Error(`Desktop queued the message instead of sending it: ${latestSystem}`);
      }
      if (latestSystem.startsWith("خطأ:")) {
        throw new Error(latestSystem);
      }
      if (assistantMessages.length > previousAssistantCount) {
        return snapshot;
      }
      return null;
    },
    { timeoutMs: 120000, intervalMs: 1000, label: "assistant response" },
  );
}

async function main() {
  const win = await waitFor(() => BrowserWindow.getAllWindows()[0], { timeoutMs: 30000, label: "Electron window" });
  win.show();
  win.focus();

  await waitFor(() => !win.webContents.isLoadingMainFrame(), { timeoutMs: 30000, label: "renderer load" });
  await sleep(4000);

  const readySnapshot = await waitFor(
    async () => {
      const snapshot = await getUiSnapshot(win);
      if (snapshot.activationVisible) {
        throw new Error("Activation panel is visible. Desktop session was not restored.");
      }
      if (!snapshot.employee || snapshot.employee.includes("Unknown")) {
        return null;
      }
      return snapshot;
    },
    { timeoutMs: 60000, intervalMs: 1000, label: "employee session" },
  );

  console.log("Desktop session:");
  console.log(JSON.stringify(readySnapshot, null, 2));

  await startFreshConversation(win);
  await sleep(1000);

  let snapshot = await getUiSnapshot(win);
  let assistantCount = snapshot.messages.filter((item) => item.role === "assistant" && item.text).length;

  const firstPrompt = "مرحبا. اذكر اسم الموظف الحالي والبروفايل الحالي في سطر واحد فقط.";
  console.log(`Sending prompt 1: ${firstPrompt}`);
  await sendChatMessage(win, firstPrompt);
  snapshot = await waitForAgentTurn(win, assistantCount);
  assistantCount = snapshot.messages.filter((item) => item.role === "assistant" && item.text).length;
  console.log("Assistant reply 1:");
  console.log(snapshot.messages.filter((item) => item.role === "assistant").at(-1)?.text || "");

  const secondPrompt = "ما الملفات الموجودة في المجلد المفتوح الآن؟ اذكر أسماء الملفات فقط بشكل مختصر.";
  console.log(`Sending prompt 2: ${secondPrompt}`);
  await sendChatMessage(win, secondPrompt);
  snapshot = await waitForAgentTurn(win, assistantCount);
  console.log("Assistant reply 2:");
  console.log(snapshot.messages.filter((item) => item.role === "assistant").at(-1)?.text || "");

  console.log("Desktop test completed. The Electron window will remain open.");
}

app.whenReady().then(() => {
  main().catch((error) => {
    console.error("Desktop test failed:", error);
  });
});
