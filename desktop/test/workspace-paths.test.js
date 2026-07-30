const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { resolveWorkspaceFile } = require("../src/main/workspace-paths");

test("workspace paths reject traversal and symlink/junction escapes", (t) => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "fqsaas-path-test-"));
  t.after(() => fs.rmSync(tempRoot, { recursive: true, force: true }));

  const workspace = path.join(tempRoot, "workspace");
  const outside = path.join(tempRoot, "outside");
  fs.mkdirSync(workspace);
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "secret.txt"), "secret");

  assert.throws(() => resolveWorkspaceFile(workspace, "../outside/secret.txt"), /escapes/);
  assert.equal(
    resolveWorkspaceFile(workspace, "new/folder/file.txt").target,
    path.join(workspace, "new", "folder", "file.txt"),
  );

  const link = path.join(workspace, "external");
  fs.symlinkSync(outside, link, process.platform === "win32" ? "junction" : "dir");
  assert.throws(() => resolveWorkspaceFile(workspace, "external/secret.txt"), /outside/);
  assert.throws(() => resolveWorkspaceFile(workspace, "external/new.txt"), /outside/);
});
