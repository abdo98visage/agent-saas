const { app, BrowserWindow, ipcMain, dialog, shell, session: electronSession, autoUpdater, safeStorage } = require("electron");
const Store = require("electron-store");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { resolveWorkspaceFile, toRealDir } = require("./workspace-paths");

const pendingWrites = new Map();
const PENDING_WRITE_TTL_MS = 10 * 60 * 1000;
const ACTIVATION_PROTOCOL = "fqsaas";

let mainWindow;
let pendingActivationUrl = "";
let rendererHasUnsavedChanges = false;

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
    if (app.isPackaged) {
      throw new Error("Secure credential storage is unavailable on this device");
    }
    return `development-plaintext:${token}`;
  }
  return safeStorage.encryptString(token).toString("base64");
}

function decryptToken(value) {
  if (!value) {
    return "";
  }
  if (!safeStorage.isEncryptionAvailable()) {
    if (app.isPackaged) {
      return "";
    }
    return value.startsWith("development-plaintext:")
      ? value.slice("development-plaintext:".length)
      : "";
  }
  try {
    return safeStorage.decryptString(Buffer.from(value, "base64"));
  } catch {
    return "";
  }
}

function buildRendererSettings() {
  const rawStore = { ...store.store };
  const encryptedToken = typeof rawStore.token === "string" ? rawStore.token : "";
  const encryptedRefreshToken = typeof rawStore.refreshToken === "string" ? rawStore.refreshToken : "";
  let offlineQueue = Array.isArray(rawStore.offlineQueue) ? rawStore.offlineQueue : [];
  if (rawStore.offlineQueueEncrypted) {
    try {
      offlineQueue = JSON.parse(decryptToken(String(rawStore.offlineQueueEncrypted)));
    } catch {
      offlineQueue = [];
    }
  }
  return {
    ...rawStore,
    token: decryptToken(encryptedToken),
    refreshToken: "",
    hasRefreshSession: Boolean(decryptToken(encryptedRefreshToken)),
    offlineQueue: Array.isArray(offlineQueue) ? offlineQueue : [],
    offlineQueueEncrypted: undefined,
    selectedProjectFiles: Array.isArray(rawStore.selectedProjectFiles) ? rawStore.selectedProjectFiles : [],
    projects: Array.isArray(rawStore.projects) ? rawStore.projects : [],
    conversationProjectMap: rawStore.conversationProjectMap && typeof rawStore.conversationProjectMap === "object" ? rawStore.conversationProjectMap : {},
    currentProjectId: typeof rawStore.currentProjectId === "string" ? rawStore.currentProjectId : null,
  };
}

function stripUndefinedValues(value) {
  if (Array.isArray(value)) {
    return value.map(stripUndefinedValues);
  }
  if (!value || typeof value !== "object") {
    return value;
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, entryValue]) => entryValue !== undefined)
      .map(([key, entryValue]) => [key, stripUndefinedValues(entryValue)])
  );
}

function normalizeApiUrl(serverUrl) {
  const parsed = new URL(serverUrl);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Activation server must use http or https");
  }
  if (app.isPackaged && parsed.protocol !== "https:") {
    throw new Error("Packaged releases require an HTTPS activation server");
  }
  parsed.hash = "";
  parsed.search = "";
  parsed.pathname = parsed.pathname.replace(/\/$/, "");
  if (!parsed.pathname.endsWith("/api")) {
    parsed.pathname = `${parsed.pathname}/api`.replace(/\/+/g, "/");
  }
  const normalized = parsed.toString().replace(/\/$/, "");
  if (!TRUSTED_API_ORIGINS.has(parsed.origin)) {
    throw new Error("Activation server is not trusted by this desktop release");
  }
  return normalized;
}

function parseActivationUrl(rawUrl) {
  const parsed = new URL(rawUrl);
  if (parsed.protocol !== `${ACTIVATION_PROTOCOL}:`) {
    return null;
  }
  const token = parsed.searchParams.get("token") || "";
  const server = parsed.searchParams.get("server") || "";
  if (!token || !server) {
    return null;
  }
  return {
    token,
    apiUrl: normalizeApiUrl(server),
  };
}

function applyActivationUrl(rawUrl) {
  let activation;
  try {
    activation = parseActivationUrl(rawUrl);
  } catch (error) {
    console.warn("Invalid activation URL:", error.message);
    return false;
  }
  if (!activation) {
    return false;
  }
  store.set({
    activationApiUrl: activation.apiUrl,
    apiUrl: activation.apiUrl,
  });
  if (mainWindow) {
    mainWindow.webContents.send("activation-link", activation);
    mainWindow.show();
    mainWindow.focus();
  }
  return true;
}

function findActivationArg(argv) {
  return argv.find((arg) => typeof arg === "string" && arg.startsWith(`${ACTIVATION_PROTOCOL}://`)) || "";
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
const API_URL = process.env.API_URL || desktopConfig.apiUrl || "http://localhost:8001/api";
const TRUSTED_API_ORIGINS = new Set(
  [API_URL, ...(Array.isArray(desktopConfig.allowedApiOrigins) ? desktopConfig.allowedApiOrigins : [])]
    .map((value) => {
      try {
        return new URL(value).origin;
      } catch {
        return "";
      }
    })
    .filter(Boolean),
);
const EXCLUDED_DIRS = [".git", "node_modules", ".venv", "__pycache__", "venv", "build", "dist", ".next", ".cache"];
const EXCLUDED_FILES = [".gitignore", "package-lock.json", "yarn.lock"];
const EXCLUDED_FILE_PREFIXES = [".env"];
const EXCLUDED_FILE_EXTENSIONS = new Set([".pem", ".key", ".p12", ".pfx", ".crt"]);
const SECRET_FILE_PATTERNS = [/secret/i, /credential/i, /private[-_]?key/i];
const TEXT_EXTENSIONS = new Set([".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".xml", ".sql", ".sh", ".bat", ".cfg", ".ini", ".conf"]);
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"]);
const MAX_FILE_SIZE = 2 * 1024 * 1024;
const MAX_IMAGE_FILE_SIZE = 6 * 1024 * 1024;
const MAX_SNIPPET_LENGTH = 600;
const MAX_CONTEXT_FILE_CHARS = 1500;
const MAX_CONTEXT_TOTAL_CHARS = 9000;
const MAX_CONTEXT_FILES = 6;
const MAX_WORKSPACE_FILES = 5000;
const MAX_WORKSPACE_DEPTH = 20;
const UPDATE_FEED_URL = process.env.UPDATE_FEED_URL || "";
const updateStatus = {
  configured: Boolean(UPDATE_FEED_URL),
  packaged: app.isPackaged,
  state: "idle",
  message: UPDATE_FEED_URL ? "Update feed configured" : "UPDATE_FEED_URL is not configured",
  lastCheckedAt: null,
};
const TRUSTED_CONNECT_SOURCES = Array.from(TRUSTED_API_ORIGINS).flatMap((origin) => {
  const parsed = new URL(origin);
  const websocketProtocol = parsed.protocol === "https:" ? "wss:" : "ws:";
  return [parsed.origin, `${websocketProtocol}//${parsed.host}`];
});
const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: ${Array.from(TRUSTED_API_ORIGINS).join(" ")}`,
  `connect-src 'self' ${TRUSTED_CONNECT_SOURCES.join(" ")}`,
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
  autoUpdater.on("update-downloaded", async () => {
    updateStatus.state = "downloaded";
    updateStatus.message = "Update downloaded; restart when ready";
    const hasPendingWork = rendererHasUnsavedChanges || pendingWrites.size > 0;
    const result = await dialog.showMessageBox(mainWindow, {
      type: "info",
      title: "Update ready",
      message: hasPendingWork
        ? "The update is ready, but there are unapplied or unsaved changes."
        : "The update is ready to install.",
      detail: hasPendingWork
        ? "Save or apply your changes, then restart the application."
        : "Restart now or install automatically when you close the application.",
      buttons: hasPendingWork ? ["Later"] : ["Restart now", "Later"],
      defaultId: hasPendingWork ? 0 : 1,
      cancelId: hasPendingWork ? 0 : 1,
    });
    if (!hasPendingWork && result.response === 0) {
      autoUpdater.quitAndInstall();
    }
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
  if (pendingActivationUrl) {
    mainWindow.webContents.once("did-finish-load", () => {
      applyActivationUrl(pendingActivationUrl);
      pendingActivationUrl = "";
    });
  }
}

function sanitizeArtifactFileName(fileName) {
  const normalized = String(fileName || "").trim().replace(/[<>:"/\\|?*\x00-\x1F]/g, "_");
  return normalized || `artifact-${Date.now()}.txt`;
}

function ensureArtifactDownloadsDir() {
  const downloadsRoot = app.getPath("downloads") || path.join(os.homedir(), "Downloads");
  const targetDir = path.join(downloadsRoot, "KarzounOS");
  fs.mkdirSync(targetDir, { recursive: true });
  return targetDir;
}

function getConversationWorkspaceRoot() {
  return toRealDir(ensureArtifactDownloadsDir());
}

function saveConversationArtifact(fileName, content) {
  const artifactDir = ensureArtifactDownloadsDir();
  const safeName = sanitizeArtifactFileName(fileName);
  const parsed = path.parse(safeName);
  let target = path.join(artifactDir, safeName);
  let suffix = 1;

  while (fs.existsSync(target)) {
    target = path.join(artifactDir, `${parsed.name}-${suffix}${parsed.ext}`);
    suffix += 1;
  }

  fs.writeFileSync(target, String(content || ""), "utf-8");
  return {
    ok: true,
    path: target,
    directory: artifactDir,
    fileName: path.basename(target),
  };
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

function readTextFileWithFallback(filePath) {
  const encodings = ["utf-8", "utf8", "latin1"];

  for (const encoding of encodings) {
    try {
      const content = fs.readFileSync(filePath, { encoding });
      if (typeof content === "string" && content.length > 0) {
        return content;
      }
    } catch {
      // Continue to the next fallback.
    }
  }

  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return "";
  }
}

function hashFileState(filePath) {
  if (!fs.existsSync(filePath)) {
    return null;
  }
  const stat = fs.lstatSync(filePath);
  if (!stat.isFile()) {
    throw new Error(`Workspace changes only support files: ${filePath}`);
  }
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function createPreviewToken() {
  return crypto.randomUUID();
}

function consumePendingWrite(previewToken, expectedType) {
  const pending = pendingWrites.get(previewToken);
  pendingWrites.delete(previewToken);
  if (!pending || pending.type !== expectedType) {
    throw new Error("Invalid or expired workspace change token");
  }
  if (Date.now() - pending.createdAt > PENDING_WRITE_TTL_MS) {
    throw new Error("Workspace change token has expired");
  }
  return pending;
}

function assertUnchanged(preconditions) {
  for (const precondition of preconditions) {
    if (hashFileState(precondition.target) !== precondition.hash) {
      throw new Error(`File changed after preview: ${precondition.path}`);
    }
  }
}

function atomicWriteFile(target, content) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const nonce = crypto.randomUUID();
  const temp = `${target}.fqsaas-${nonce}.tmp`;
  const backup = `${target}.fqsaas-${nonce}.bak`;
  fs.writeFileSync(temp, content);
  let hadPrevious = false;
  try {
    if (fs.existsSync(target)) {
      fs.renameSync(target, backup);
      hadPrevious = true;
    }
    fs.renameSync(temp, target);
    if (hadPrevious && fs.existsSync(backup)) {
      fs.unlinkSync(backup);
    }
  } catch (error) {
    if (fs.existsSync(temp)) {
      fs.unlinkSync(temp);
    }
    if (hadPrevious && fs.existsSync(backup) && !fs.existsSync(target)) {
      fs.renameSync(backup, target);
    }
    throw error;
  }
}

function snapshotFiles(filePaths) {
  return Array.from(new Set(filePaths)).map((target) => ({
    target,
    content: fs.existsSync(target) ? fs.readFileSync(target) : null,
  }));
}

function restoreSnapshots(snapshots) {
  for (const snapshot of snapshots) {
    if (snapshot.content === null) {
      if (fs.existsSync(snapshot.target)) {
        fs.unlinkSync(snapshot.target);
      }
    } else {
      atomicWriteFile(snapshot.target, snapshot.content);
    }
  }
}

async function scanWorkspace(rootPath) {
  const root = toRealDir(rootPath);
  const files = [];

  async function scan(dir, relativeDir = "", depth = 0) {
    if (depth > MAX_WORKSPACE_DEPTH || files.length >= MAX_WORKSPACE_FILES) {
      return;
    }
    const entries = await fs.promises.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (files.length >= MAX_WORKSPACE_FILES) {
        break;
      }
      const fullPath = path.join(dir, entry.name);
      const relativePath = relativeDir ? path.join(relativeDir, entry.name) : entry.name;

      if (entry.isDirectory()) {
        if (entry.isSymbolicLink() || EXCLUDED_DIRS.includes(entry.name)) {
          continue;
        }
        await scan(fullPath, relativePath, depth + 1);
        continue;
      }

      const ext = path.extname(entry.name).toLowerCase();
      const isImage = IMAGE_EXTENSIONS.has(ext);
      if (!isImage && !isIncludedFile(entry.name, fullPath)) {
        continue;
      }

      const stat = fs.statSync(fullPath);
      const content = isImage ? "[image file]" : readTextFileWithFallback(fullPath);
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
        kind: isImage ? "image" : "text",
        snippet: sanitizeSnippet(content),
      });
      if (files.length % 50 === 0) {
        await new Promise((resolve) => setImmediate(resolve));
      }
    }
  }

  await scan(root);
  return files.sort((left, right) => left.path.localeCompare(right.path));
}

function imageFileToDataUrl(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (!IMAGE_EXTENSIONS.has(ext)) {
    throw new Error("Only image files are supported");
  }
  const stat = fs.statSync(filePath);
  if (stat.size > MAX_IMAGE_FILE_SIZE) {
    throw new Error("Image file is too large");
  }
  const mimeType = ext === ".png"
    ? "image/png"
    : ext === ".gif"
      ? "image/gif"
      : ext === ".webp"
        ? "image/webp"
        : ext === ".bmp"
          ? "image/bmp"
          : "image/jpeg";
  const buffer = fs.readFileSync(filePath);
  return {
    name: path.basename(filePath),
    mimeType,
    size: stat.size,
    dataUrl: `data:${mimeType};base64,${buffer.toString("base64")}`,
    modifiedAt: stat.mtime.toISOString(),
  };
}

async function buildProjectContext(rootPath, query, selectedPaths = []) {
  const root = toRealDir(rootPath);
  const queryTokens = String(query || "")
    .toLowerCase()
    .split(/[^a-z0-9_]+/i)
    .filter(Boolean);

  const workspaceFiles = await scanWorkspace(root);
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
    const ext = path.extname(file.path).toLowerCase();
    const content = IMAGE_EXTENSIONS.has(ext)
      ? `[image file: ${path.basename(file.path)}]`
      : readTextFileWithFallback(target).slice(0, MAX_CONTEXT_FILE_CHARS);
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

async function listWorkspaceFiles(rootPath, options = {}) {
  const query = String(options.query || "").toLowerCase();
  const limit = Math.min(Math.max(Number(options.limit || 50), 1), 200);
  const files = (await scanWorkspace(rootPath))
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

async function searchWorkspaceFiles(rootPath, query, limit = 20) {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) {
    return { matches: [], count: 0 };
  }
  const maxResults = Math.min(Math.max(Number(limit || 20), 1), 100);
  const files = await scanWorkspace(rootPath);
  const matches = [];

  for (const file of files) {
    if (matches.length >= maxResults) {
      break;
    }
    const { target } = resolveWorkspaceFile(rootPath, file.path);
    const content = readTextFileWithFallback(target);
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
      content: readTextFileWithFallback(target),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
    });
  }
  return { files, count: files.length };
}

function prepareWorkspaceChanges(rootPath, changes = []) {
  const previewToken = createPreviewToken();
  const operations = [];
  const preconditions = [];
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
      preconditions.push({ target: source, path: change.path, hash: hashFileState(source) });
      preconditions.push({ target, path: change.new_path, hash: hashFileState(target) });
      operations.push({ action, source, target, path: change.path, newPath: change.new_path });
      summary.renamedFiles.push({ from: change.path, to: change.new_path });
      continue;
    }
    if (action === "delete") {
      const target = resolveWorkspaceFile(rootPath, change.path).target;
      preconditions.push({ target, path: change.path, hash: hashFileState(target) });
      operations.push({ action, target, path: change.path });
      summary.deletedFiles.push(change.path);
      continue;
    }

    const targetPath = resolveWorkspaceFile(rootPath, change.path).target;
    const previousContent = fs.existsSync(targetPath) ? readTextFileWithFallback(targetPath) : "";
    preconditions.push({ target: targetPath, path: change.path, hash: hashFileState(targetPath) });
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
  pendingWrites.set(previewToken, {
    type: "workspace_changes",
    operations,
    preconditions,
    createdAt: Date.now(),
  });
  return { previewToken, summary };
}

function applyWorkspaceChanges(previewToken) {
  const pending = consumePendingWrite(previewToken, "workspace_changes");
  assertUnchanged(pending.preconditions);

  const changedFiles = [];
  const snapshots = snapshotFiles(
    pending.operations.flatMap((operation) => [operation.source, operation.target].filter(Boolean)),
  );
  try {
    for (const operation of pending.operations) {
      if (operation.action === "rename") {
        if (!fs.existsSync(operation.source)) {
          throw new Error(`Rename source no longer exists: ${operation.path}`);
        }
        if (fs.existsSync(operation.target)) {
          throw new Error(`Rename target already exists: ${operation.newPath}`);
        }
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

      atomicWriteFile(operation.target, operation.nextContent);
      changedFiles.push(operation.path);
    }
  } catch (error) {
    restoreSnapshots(snapshots);
    throw error;
  }

  return { ok: true, changedFiles };
}

const startupActivationUrl = findActivationArg(process.argv);
if (startupActivationUrl) {
  pendingActivationUrl = startupActivationUrl;
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    const activationUrl = findActivationArg(argv);
    if (activationUrl) {
      applyActivationUrl(activationUrl);
    }
  });

  app.on("open-url", (event, url) => {
    event.preventDefault();
    if (!applyActivationUrl(url)) {
      pendingActivationUrl = url;
    }
  });

  app.whenReady().then(() => {
    app.setAsDefaultProtocolClient(ACTIVATION_PROTOCOL);
    setupSecurity();
    configureAutoUpdates();
    createWindow();
  });
}
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
  const nextSettings = stripUndefinedValues({ ...settings });
  if (Array.isArray(nextSettings.offlineQueue)) {
    nextSettings.offlineQueueEncrypted = encryptToken(JSON.stringify(nextSettings.offlineQueue));
    delete nextSettings.offlineQueue;
    store.delete("offlineQueue");
  }
  if (!nextSettings.refreshToken) {
    delete nextSettings.refreshToken;
  }
  for (const key of ["token", "refreshToken"]) {
    if (Object.prototype.hasOwnProperty.call(nextSettings, key)) {
      nextSettings[key] = encryptToken(String(nextSettings[key] || ""));
    }
  }
  store.set(nextSettings);
  return {
    apiUrl: API_URL,
    ...buildRendererSettings(),
  };
});

ipcMain.handle("clear-desktop-session", () => {
  store.set({ token: "", refreshToken: "" });
  return { ok: true };
});

ipcMain.handle("activate-desktop-session", async (_, apiUrl, inviteToken, password) => {
  const normalizedApiUrl = String(apiUrl || API_URL).replace(/\/$/, "");
  const parsedApiUrl = new URL(normalizedApiUrl);
  if (!TRUSTED_API_ORIGINS.has(parsedApiUrl.origin)) {
    throw new Error("Untrusted API origin");
  }
  const response = await fetch(`${normalizedApiUrl}/auth/activate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Type": "desktop",
    },
    body: JSON.stringify({ token: inviteToken, password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.access_token || !data.refresh_token) {
    throw new Error(data.detail || "Failed to activate");
  }
  store.set({
    token: encryptToken(data.access_token),
    refreshToken: encryptToken(data.refresh_token),
  });
  return { accessToken: data.access_token };
});

ipcMain.handle("refresh-desktop-session", async (_, apiUrl) => {
  const parsedApiUrl = new URL(String(apiUrl || API_URL));
  if (!TRUSTED_API_ORIGINS.has(parsedApiUrl.origin)) {
    throw new Error("Untrusted API origin");
  }
  const rawRefreshToken = decryptToken(String(store.get("refreshToken") || ""));
  if (!rawRefreshToken) {
    throw new Error("Missing refresh session");
  }
  const response = await fetch(`${String(apiUrl || API_URL).replace(/\/$/, "")}/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Client-Type": "desktop",
    },
    body: JSON.stringify({ refresh_token: rawRefreshToken }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.access_token || !data.refresh_token) {
    store.set({ token: "", refreshToken: "" });
    throw new Error(data.detail || "Session refresh failed");
  }
  store.set({
    token: encryptToken(data.access_token),
    refreshToken: encryptToken(data.refresh_token),
  });
  return { accessToken: data.access_token };
});

ipcMain.handle("parse-activation-url", (_, rawUrl) => parseActivationUrl(rawUrl));

ipcMain.handle("get-update-status", () => ({ ...updateStatus }));
ipcMain.handle("set-renderer-dirty-state", (_, isDirty) => {
  rendererHasUnsavedChanges = Boolean(isDirty);
  return { ok: true };
});

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
    const files = await scanWorkspace(folderPath);
    return { files, count: files.length };
  } catch (error) {
    return { files: [], error: error.message };
  }
});

ipcMain.handle("get-default-workspace-root", async () => {
  try {
    return { path: getConversationWorkspaceRoot() };
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("list-files", async (_, rootPath, options) => {
  try {
    return await listWorkspaceFiles(rootPath, options || {});
  } catch (error) {
    return { files: [], error: error.message };
  }
});

ipcMain.handle("search-files", async (_, rootPath, query, limit) => {
  try {
    return await searchWorkspaceFiles(rootPath, query, limit);
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
      content: readTextFileWithFallback(target),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
    };
  } catch (error) {
    return { error: error.message };
  }
});

ipcMain.handle("read-image-file", async (_, rootPath, filePath) => {
  try {
    const { target } = resolveWorkspaceFile(rootPath, filePath);
    return imageFileToDataUrl(target);
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
    return await buildProjectContext(rootPath, query, selectedPaths);
  } catch (error) {
    return { context: "", files: [], error: error.message };
  }
});

ipcMain.handle("prepare-file-write", async (_, rootPath, filePath, nextContent) => {
  try {
    const { target } = resolveWorkspaceFile(rootPath, filePath);
    const previousContent = fs.existsSync(target) ? fs.readFileSync(target, "utf-8") : "";
    const previewToken = createPreviewToken();
    const summary = buildDiffSummary(previousContent, String(nextContent));

    pendingWrites.set(previewToken, {
      type: "file_write",
      target,
      nextContent: String(nextContent),
      preconditions: [{ target, path: filePath, hash: hashFileState(target) }],
      createdAt: Date.now(),
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
    const pending = consumePendingWrite(previewToken, "file_write");
    assertUnchanged(pending.preconditions);
    atomicWriteFile(pending.target, pending.nextContent);
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

ipcMain.handle("save-conversation-artifact", async (_, fileName, content) => {
  try {
    return saveConversationArtifact(fileName, content);
  } catch (error) {
    return { ok: false, error: error.message };
  }
});

console.log("FQ-SaaS Desktop initialized");
