const { app, BrowserWindow, ipcMain, dialog, shell, session: electronSession, autoUpdater, safeStorage } = require("electron");
const Store = require("electron-store");
const fs = require("fs");
const path = require("path");

const pendingWrites = new Map();

let mainWindow;

function stripBom(value) {
  return typeof value === "string" ? value.replace(/^\uFEFF/, "") : value;
}

const store = new Store({
  deserialize: (value) => JSON.parse(stripBom(value)),
  serialize: (value) => JSON.stringify(value, null, 2),
});

function encryptToken(token) {
  if (!token) {
    return "";
  }
  if (!safeStorage.isEncryptionAvailable()) {
    return token;
  }
  return safeStorage.encryptString(token).toString("base64");
}

function decryptToken(value) {
  if (!value) {
    return "";
  }
  if (!safeStorage.isEncryptionAvailable()) {
    return value;
  }
  try {
    return safeStorage.decryptString(Buffer.from(value, "base64"));
  } catch {
    return value;
  }
}

function buildRendererSettings() {
  const rawStore = { ...store.store };
  const encryptedToken = typeof rawStore.token === "string" ? rawStore.token : "";
  return {
    ...rawStore,
    token: decryptToken(encryptedToken),
    offlineQueue: Array.isArray(rawStore.offlineQueue) ? rawStore.offlineQueue : [],
    selectedProjectFiles: Array.isArray(rawStore.selectedProjectFiles) ? rawStore.selectedProjectFiles : [],
    projects: Array.isArray(rawStore.projects) ? rawStore.projects : [],
    conversationProjectMap: rawStore.conversationProjectMap && typeof rawStore.conversationProjectMap === "object" ? rawStore.conversationProjectMap : {},
    currentProjectId: typeof rawStore.currentProjectId === "string" ? rawStore.currentProjectId : null,
  };
}

function readDesktopConfig() {
  const candidates = [
    path.join(app.getAppPath(), "desktop-config.json"),
    path.join(__dirname, "..", "..", "desktop-config.json"),
  ];

  for (const configPath of candidates) {
    try {
      if (fs.existsSync(configPath)) {
        return JSON.parse(stripBom(fs.readFileSync(configPath, "utf-8")));
      }
    } catch (error) {
      console.warn("Failed to read desktop config:", error.message);
    }
  }

  return {};
}

const desktopConfig = readDesktopConfig();
const API_URL = process.env.API_URL || desktopConfig.apiUrl || "http://localhost:8002/api";
const EXCLUDED_DIRS = [".git", "node_modules", ".venv", "__pycache__", "venv", "build", "dist", ".next", ".cache"];
const EXCLUDED_FILES = [".gitignore", "package-lock.json", "yarn.lock"];
const EXCLUDED_FILE_PREFIXES = [".env"];
const EXCLUDED_FILE_EXTENSIONS = new Set([".pem", ".key", ".p12", ".pfx", ".crt"]);
const SECRET_FILE_PATTERNS = [/secret/i, /credential/i, /private[-_]?key/i];
const TEXT_EXTENSIONS = new Set([".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".xml", ".sql", ".sh", ".bat", ".cfg", ".ini", ".conf"]);
const MAX_FILE_SIZE = 2 * 1024 * 1024;
const MAX_SNIPPET_LENGTH = 600;
const MAX_CONTEXT_FILE_CHARS = 1500;
const MAX_CONTEXT_TOTAL_CHARS = 9000;
const MAX_CONTEXT_FILES = 6;
const UPDATE_FEED_URL = process.env.UPDATE_FEED_URL || "";
const updateStatus = {
  configured: Boolean(UPDATE_FEED_URL),
  packaged: app.isPackaged,
  state: "idle",
  message: UPDATE_FEED_URL ? "Update feed configured" : "UPDATE_FEED_URL is not configured",
  lastCheckedAt: null,
};
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data:",
  "connect-src http: https: ws: wss:",
  "font-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "frame-ancestors 'none'",
].join("; ");

function setupSecurity() {
  electronSession.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    if (permission === "media" || permission === "audioCapture") {
      callback(true);
      return;
    }
    callback(false);
  });

  electronSession.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [CSP],
        "X-Content-Type-Options": ["nosniff"],
        "Referrer-Policy": ["no-referrer"],
      },
    });
  });
}

function configureAutoUpdates() {
  if (!UPDATE_FEED_URL || !app.isPackaged) {
    return;
  }

  autoUpdater.setFeedURL({ url: UPDATE_FEED_URL });
  autoUpdater.on("checking-for-update", () => {
    updateStatus.state = "checking";
    updateStatus.message = "Checking for updates";
    updateStatus.lastCheckedAt = new Date().toISOString();
  });
  autoUpdater.on("update-available", () => {
    updateStatus.state = "available";
    updateStatus.message = "Update available";
  });
  autoUpdater.on("update-not-available", () => {
    updateStatus.state = "current";
    updateStatus.message = "App is up to date";
  });
  autoUpdater.on("error", (error) => {
    updateStatus.state = "error";
    updateStatus.message = error.message;
    console.error("Auto-update error:", error.message);
  });
  autoUpdater.on("update-downloaded", () => {
    updateStatus.state = "downloaded";
    updateStatus.message = "Update downloaded; installing";
    autoUpdater.quitAndInstall();
  });
  setTimeout(() => {
    autoUpdater.checkForUpdates();
  }, 30000);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: "FQ-SaaS Workspace",
    webPreferences: {
      preload: path.join(__dirname, "..", "preload", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  mainWindow.webContents.on("will-navigate", (event) => {
    event.preventDefault();
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
}

function toRealDir(rootPath) {
  if (!rootPath) {
    throw new Error("Workspace path is required");
  }

  const resolved = fs.realpathSync(rootPath);
  const stat = fs.statSync(resolved);
  if (!stat.isDirectory()) {
    throw new Error("Workspace path must be a directory");
  }

  return resolved;
}

function resolveWorkspaceFile(rootPath, relativePath) {
  const root = toRealDir(rootPath);
  const target = path.resolve(root, relativePath || "");
  const normalizedRoot = root.endsWith(path.sep) ? root : `${root}${path.sep}`;

  if (target !== root && !target.startsWith(normalizedRoot)) {
    throw new Error("File path escapes the selected workspace");
  }

  return { root, target };
}

function isIncludedFile(entryName, fullPath) {
  if (EXCLUDED_FILES.includes(entryName)) {
    return false;
  }
  if (EXCLUDED_FILE_PREFIXES.some((prefix) => entryName.startsWith(prefix))) {
    return false;
  }
  if (SECRET_FILE_PATTERNS.some((pattern) => pattern.test(entryName))) {
    return false;
  }

  const ext = path.extname(entryName).toLowerCase();
  if (EXCLUDED_FILE_EXTENSIONS.has(ext)) {
    return false;
  }
  if (!TEXT_EXTENSIONS.has(ext)) {
    return false;
  }

  const stat = fs.statSync(fullPath);
  return stat.isFile() && stat.size <= MAX_FILE_SIZE;
}

function sanitizeSnippet(content) {
  return content.slice(0, MAX_SNIPPET_LENGTH).replace(/\0/g, "");
}

function scanWorkspace(rootPath) {
  const root = toRealDir(rootPath);
  const files = [];

  function scan(dir, relativeDir = "") {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      const relativePath = relativeDir ? path.join(relativeDir, entry.name) : entry.name;

      if (entry.isDirectory()) {
        if (EXCLUDED_DIRS.includes(entry.name)) {
          continue;
        }
        scan(fullPath, relativePath);
        continue;
      }

      if (!isIncludedFile(entry.name, fullPath)) {
        continue;
      }

      const stat = fs.statSync(fullPath);
      const content = fs.readFileSync(fullPath, "utf-8");
      const createdAt = stat.birthtime instanceof Date ? stat.birthtime : stat.mtime;
      const status = Math.abs(stat.mtimeMs - stat.birthtimeMs) < 60_000
        ? "new"
        : "modified";
      files.push({
        path: relativePath,
        size: stat.size,
        createdAt: createdAt.toISOString(),
        modifiedAt: stat.mtime.toISOString(),
        status,
        snippet: sanitizeSnippet(content),
      });
    }
  }

  scan(root);
  return files.sort((left, right) => left.path.localeCompare(right.path));
}

function buildProjectContext(rootPath, query, selectedPaths = []) {
  const root = toRealDir(rootPath);
  const queryTokens = String(query || "")
    .toLowerCase()
    .split(/[^a-z0-9_]+/i)
    .filter(Boolean);

  const workspaceFiles = scanWorkspace(root);
  const selectedSet = new Set((selectedPaths || []).filter(Boolean));

  const scored = workspaceFiles
    .map((file) => {
      let score = 0;
      const haystack = `${file.path}\n${file.snippet}`.toLowerCase();

      if (selectedSet.has(file.path)) {
        score += 100;
      }

      for (const token of queryTokens) {
        if (haystack.includes(token)) {
          score += 10;
        }
      }

      return { ...file, score };
    })
    .filter((file) => file.score > 0 || selectedSet.has(file.path))
    .sort((left, right) => right.score - left.score || left.path.localeCompare(right.path))
    .slice(0, MAX_CONTEXT_FILES);

  const chunks = [];
  let totalChars = 0;

  for (const file of scored) {
    const { target } = resolveWorkspaceFile(root, file.path);
    const content = fs.readFileSync(target, "utf-8").slice(0, MAX_CONTEXT_FILE_CHARS);
    const block = `${file.path}:\n${content}`;
    if (totalChars + block.length > MAX_CONTEXT_TOTAL_CHARS) {
      break;
    }
    totalChars += block.length;
    chunks.push(block);
  }

  return {
    context: chunks.join("\n\n---\n\n"),
    files: scored.map((file) => ({ path: file.path, score: file.score })),
    truncated: totalChars >= MAX_CONTEXT_TOTAL_CHARS,
  };
}

function buildDiffSummary(previousContent, nextContent) {
  const previousLines = previousContent.split(/\r?\n/);
  const nextLines = nextContent.split(/\r?\n/);
  let changedLines = 0;
  const maxLines = Math.max(previousLines.length, nextLines.length);

  for (let index = 0; index < maxLines; index += 1) {
    if ((previousLines[index] || "") !== (nextLines[index] || "")) {
      changedLines += 1;
    }
  }

  return {
    previousLineCount: previousLines.length,
    nextLineCount: nextLines.length,
    changedLines,
  };
}

function listWorkspaceFiles(rootPath, options = {}) {
  const query = String(options.query || "").toLowerCase();
  const limit = Math.min(Math.max(Number(options.limit || 50), 1), 200);
  const files = scanWorkspace(rootPath)
    .filter((file) => !query || file.path.toLowerCase().includes(query) || file.snippet.toLowerCase().includes(query))
    .slice(0, limit);
  return {
    files: files.map((file) => ({
      path: file.path,
      size: file.size,
      modifiedAt: file.modifiedAt,
      snippet: file.snippet,
    })),
    count: files.length,
  };
}

function searchWorkspaceFiles(rootPath, query, limit = 20) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return { matches: [], count: 0 };
  }
  const maxResults = Math.min(Math.max(Number(limit || 20), 1), 100);
  const files = scanWorkspace(rootPath);
  const matches = [];

  for (const file of files) {
    if (matches.length >= maxResults) {
      break;
    }
    const { target } = resolveWorkspaceFile(rootPath, file.path);
    const content = fs.readFileSync(target, "utf-8");
    const lines = content.split(/\r?\n/);
    for (let index = 0; index < lines.length; index += 1) {
      if (lines[index].toLowerCase().includes(normalizedQuery)) {
        matches.push({
          path: file.path,
          line: index + 1,
          snippet: lines[index].slice(0, 500),
        });
        if (matches.length >= maxResults) {
          break;
        }
      }
    }
  }

  return { matches, count: matches.length };
}

function readMultipleWorkspaceFiles(rootPath, filePaths = []) {
  const files = [];
  for (const filePath of filePaths.slice(0, 20)) {
    const { target } = resolveWorkspaceFile(rootPath, filePath);
    const stat = fs.statSync(target);
    if (stat.size > MAX_FILE_SIZE) {
      files.push({ path: filePath, error: "File too large" });
      continue;
    }
    files.push({
      path: filePath,
      content: fs.readFileSync(target, "utf-8"),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
    });
  }
  return { files, count: files.length };
}

function prepareWorkspaceChanges(rootPath, changes = []) {
  const previewToken = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const operations = [];
  const summary = {
    changedFiles: [],
    createdFiles: [],
    renamedFiles: [],
    deletedFiles: [],
    totalOperations: 0,
    changedLines: 0,
  };

  for (const change of changes.slice(0, 50)) {
    const action = String(change.action || "update");
    if (action === "rename") {
      const source = resolveWorkspaceFile(rootPath, change.path).target;
      const target = resolveWorkspaceFile(rootPath, change.new_path).target;
      operations.push({ action, source, target, path: change.path, newPath: change.new_path });
      summary.renamedFiles.push({ from: change.path, to: change.new_path });
      continue;
    }
    if (action === "delete") {
      const target = resolveWorkspaceFile(rootPath, change.path).target;
      operations.push({ action, target, path: change.path });
      summary.deletedFiles.push(change.path);
      continue;
    }

    const targetPath = resolveWorkspaceFile(rootPath, change.path).target;
    const previousContent = fs.existsSync(targetPath) ? fs.readFileSync(targetPath, "utf-8") : "";
    const nextContent = String(change.content || "");
    const diff = buildDiffSummary(previousContent, nextContent);
    operations.push({
      action: action === "create" ? "create" : "update",
      target: targetPath,
      path: change.path,
      nextContent,
    });
    summary.changedLines += diff.changedLines;
    if (action === "create" || !fs.existsSync(targetPath)) {
      summary.createdFiles.push(change.path);
    } else {
      summary.changedFiles.push(change.path);
    }
  }

  summary.totalOperations = operations.length;
  pendingWrites.set(previewToken, { type: "workspace_changes", operations });
  return { previewToken, summary };
}

function applyWorkspaceChanges(previewToken) {
  const pending = pendingWrites.get(previewToken);
  if (!pending || pending.type !== "workspace_changes") {
    return { error: "Invalid or expired workspace change token" };
  }

  const changedFiles = [];
  for (const operation of pending.operations) {
    if (operation.action === "rename") {
      fs.mkdirSync(path.dirname(operation.target), { recursive: true });
      fs.renameSync(operation.source, operation.target);
      changedFiles.push(operation.newPath);
      continue;
    }
    if (operation.action === "delete") {
      if (fs.existsSync(operation.target)) {
        fs.unlinkSync(operation.target);
      }
      changedFiles.push(operation.path);
      continue;
    }

    fs.mkdirSync(path.dirname(operation.target), { recursive: true });
    fs.writeFileSync(operation.target, operation.nextContent, "utf-8");
    changedFiles.push(operation.path);
  }

  pendingWrites.delete(previewToken);
  return { ok: true, changedFiles };
}

app.whenReady().then(() => {
  setupSecurity();
  configureAutoUpdates();
  createWindow();
});
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.handle("get-settings", () => ({
  apiUrl: API_URL,
  ...buildRendererSettings(),
}));

ipcMain.handle("set-settings", (_, settings) => {
  const nextSettings = { ...settings };
  if (Object.prototype.hasOwnProperty.call(nextSettings, "token")) {
    nextSettings.token = encryptToken(String(nextSettings.token || ""));
  }
  store.set(nextSettings);
  return {
    apiUrl: API_URL,
    ...buildRendererSettings(),
  };
});

ipcMain.handle("get-update-status", () => ({ ...updateStatus }));

ipcMain.handle("check-for-updates", async () => {
  updateStatus.lastCheckedAt = new Date().toISOString();
  if (!UPDATE_FEED_URL) {
    updateStatus.state = "not_configured";
    updateStatus.message = "UPDATE_FEED_URL is not configured";
    return { ...updateStatus };
  }
  if (!app.isPackaged) {
    updateStatus.state = "not_packaged";
    updateStatus.message = "Update checks require a packaged release build";
    return { ...updateStatus };
  }

  updateStatus.state = "checking";
  updateStatus.message = "Checking for updates";
  autoUpdater.checkForUpdates();
  return { ...updateStatus };
});

ipcMain.handle("open-folder", async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    title: "اختر مجلد المشروع",
  });

  return result.canceled ? null : result.filePaths[0];
});

ipcMain.handle("scan-folder", async (_, folderPath) => {
  try {
    const files = scanWorkspace(folderPath);
    return { files, count: files.length };
  } catch (error) {
    return { files: [], error: error.message };
  }
});

ipcMain.handle("list-files", async (_, rootPath, options) => {
  try {
    return listWorkspaceFiles(rootPath, options || {});
  } catch (error) {
    return { files: [], error: error.message };
  }
});

ipcMain.handle("search-files", async (_, rootPath, query, limit) => {
  try {
    return searchWorkspaceFiles(rootPath, query, limit);
  } catch (error) {
    return { matches: [], error: error.message };
  }
});

ipcMain.handle("read-file", async (_, rootPath, filePath) => {
  try {
    const { target } = resolveWorkspaceFile(rootPath, filePath);
    const stat = fs.statSync(target);
    if (stat.size > MAX_FILE_SIZE) {
      return { error: "File too large" };
    }

    return {
      content: fs.readFileSync(target, "utf-8"),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
    };
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("read-multiple-files", async (_, rootPath, filePaths) => {
  try {
    return readMultipleWorkspaceFiles(rootPath, Array.isArray(filePaths) ? filePaths : []);
  } catch (error) {
    return { files: [], error: error.message };
  }
});

ipcMain.handle("build-project-context", async (_, rootPath, query, selectedPaths) => {
  try {
    return buildProjectContext(rootPath, query, selectedPaths);
  } catch (error) {
    return { context: "", files: [], error: error.message };
  }
});

ipcMain.handle("prepare-file-write", async (_, rootPath, filePath, nextContent) => {
  try {
    const { target } = resolveWorkspaceFile(rootPath, filePath);
    const previousContent = fs.existsSync(target) ? fs.readFileSync(target, "utf-8") : "";
    const previewToken = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const summary = buildDiffSummary(previousContent, String(nextContent));

    pendingWrites.set(previewToken, {
      target,
      nextContent: String(nextContent),
    });

    return {
      previewToken,
      filePath,
      summary,
      previousPreview: previousContent.slice(0, 1200),
      nextPreview: String(nextContent).slice(0, 1200),
    };
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("apply-file-write", async (_, previewToken) => {
  try {
    const pending = pendingWrites.get(previewToken);
    if (!pending) {
      return { error: "Invalid or expired preview token" };
    }

    fs.writeFileSync(pending.target, pending.nextContent, "utf-8");
    pendingWrites.delete(previewToken);
    return { ok: true };
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("prepare-workspace-changes", async (_, rootPath, changes) => {
  try {
    return prepareWorkspaceChanges(rootPath, Array.isArray(changes) ? changes : []);
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("apply-workspace-changes", async (_, previewToken) => {
  try {
    return applyWorkspaceChanges(previewToken);
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("open-external", async (_, url) => {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only http/https URLs are allowed");
  }
  await shell.openExternal(url);
  return { ok: true };
});

console.log("FQ-SaaS Desktop initialized");
