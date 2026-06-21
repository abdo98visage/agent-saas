const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getSettings: () => ipcRenderer.invoke("get-settings"),
  setSettings: (settings) => ipcRenderer.invoke("set-settings", settings),
  openFolder: () => ipcRenderer.invoke("open-folder"),
  scanFolder: (folderPath) => ipcRenderer.invoke("scan-folder", folderPath),
  listFiles: (rootPath, options) => ipcRenderer.invoke("list-files", rootPath, options),
  searchFiles: (rootPath, query, limit) => ipcRenderer.invoke("search-files", rootPath, query, limit),
  readFile: (rootPath, filePath) => ipcRenderer.invoke("read-file", rootPath, filePath),
  readMultipleFiles: (rootPath, filePaths) => ipcRenderer.invoke("read-multiple-files", rootPath, filePaths),
  buildProjectContext: (rootPath, query, selectedPaths) => ipcRenderer.invoke("build-project-context", rootPath, query, selectedPaths),
  prepareFileWrite: (rootPath, filePath, nextContent) => ipcRenderer.invoke("prepare-file-write", rootPath, filePath, nextContent),
  applyFileWrite: (previewToken) => ipcRenderer.invoke("apply-file-write", previewToken),
  prepareWorkspaceChanges: (rootPath, changes) => ipcRenderer.invoke("prepare-workspace-changes", rootPath, changes),
  applyWorkspaceChanges: (previewToken) => ipcRenderer.invoke("apply-workspace-changes", previewToken),
  getUpdateStatus: () => ipcRenderer.invoke("get-update-status"),
  checkForUpdates: () => ipcRenderer.invoke("check-for-updates"),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
