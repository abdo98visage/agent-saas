const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
  getSettings: () => ipcRenderer.invoke("get-settings"),
  setSettings: (settings) => ipcRenderer.invoke("set-settings", settings),
  openFolder: () => ipcRenderer.invoke("open-folder"),
  scanFolder: (folderPath) => ipcRenderer.invoke("scan-folder", folderPath),
  readFile: (rootPath, filePath) => ipcRenderer.invoke("read-file", rootPath, filePath),
  buildProjectContext: (rootPath, query, selectedPaths) => ipcRenderer.invoke("build-project-context", rootPath, query, selectedPaths),
  prepareFileWrite: (rootPath, filePath, nextContent) => ipcRenderer.invoke("prepare-file-write", rootPath, filePath, nextContent),
  applyFileWrite: (previewToken) => ipcRenderer.invoke("apply-file-write", previewToken),
  openExternal: (url) => ipcRenderer.invoke("open-external", url),
});
