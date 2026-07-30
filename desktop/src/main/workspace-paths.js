const fs = require("fs");
const path = require("path");

function toRealDir(rootPath) {
  if (!rootPath) {
    throw new Error("Workspace path is required");
  }
  const resolved = fs.realpathSync(rootPath);
  if (!fs.statSync(resolved).isDirectory()) {
    throw new Error("Workspace path must be a directory");
  }
  return resolved;
}

function isInside(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
}

function nearestExistingPath(target) {
  let candidate = target;
  while (!fs.existsSync(candidate)) {
    const parent = path.dirname(candidate);
    if (parent === candidate) {
      throw new Error("Unable to resolve workspace path");
    }
    candidate = parent;
  }
  return candidate;
}

function resolveWorkspaceFile(rootPath, relativePath) {
  const root = toRealDir(rootPath);
  const target = path.resolve(root, relativePath || "");
  if (!isInside(root, target)) {
    throw new Error("File path escapes the selected workspace");
  }

  const existingPath = nearestExistingPath(target);
  const realExistingPath = fs.realpathSync(existingPath);
  if (!isInside(root, realExistingPath)) {
    throw new Error("File path resolves outside the selected workspace");
  }

  return { root, target };
}

module.exports = {
  resolveWorkspaceFile,
  toRealDir,
};
