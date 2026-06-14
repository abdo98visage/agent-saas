const { app, BrowserWindow, ipcMain, dialog, shell } = require("electron");
const Store = require("electron-store");
const fs = require("fs");
const path = require("path");

const store = new Store();
const pendingWrites = new Map();

let mainWindow;

const API_URL = process.env.API_URL || "http://localhost:8000/api";
const EXCLUDED_DIRS = [".git", "node_modules", ".venv", "__pycache__", "venv", "build", "dist", ".next", ".cache"];
const EXCLUDED_FILES = [".env", ".gitignore", "package-lock.json", "yarn.lock"];
const TEXT_EXTENSIONS = new Set([".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".yaml", ".yml", ".toml", ".xml", ".sql", ".sh", ".bat", ".cfg", ".ini", ".conf"]);
const MAX_FILE_SIZE = 2 * 1024 * 1024;
const MAX_SNIPPET_LENGTH = 600;
const MAX_CONTEXT_FILE_CHARS = 1500;
const MAX_CONTEXT_TOTAL_CHARS = 9000;
const MAX_CONTEXT_FILES = 6;

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

  const ext = path.extname(entryName).toLowerCase();
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
      files.push({
        path: relativePath,
        size: stat.size,
        modifiedAt: stat.mtime.toISOString(),
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

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());

ipcMain.handle("get-settings", () => ({
  apiUrl: API_URL,
  offlineQueue: [],
  selectedProjectFiles: [],
  ...store.store,
}));

ipcMain.handle("set-settings", (_, settings) => {
  store.set(settings);
  return {
    apiUrl: API_URL,
    offlineQueue: [],
    selectedProjectFiles: [],
    ...store.store,
  };
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

ipcMain.handle("open-external", async (_, url) => {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only http/https URLs are allowed");
  }
  await shell.openExternal(url);
  return { ok: true };
});

console.log("FQ-SaaS Desktop initialized");
