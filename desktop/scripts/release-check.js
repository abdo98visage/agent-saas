#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const requiredForRelease = [];
const warnings = [];
const allowInsecureRelease = process.env.ALLOW_INSECURE_DESKTOP_RELEASE === "true";

const updateFeedUrl = process.env.UPDATE_FEED_URL || "";
if (!updateFeedUrl) {
  requiredForRelease.push("UPDATE_FEED_URL is not set.");
}

const hasWindowsSigning =
  Boolean(process.env.CSC_LINK && process.env.CSC_KEY_PASSWORD) ||
  Boolean(process.env.WIN_CSC_LINK && process.env.WIN_CSC_KEY_PASSWORD);

if (!hasWindowsSigning) {
  requiredForRelease.push("Windows code-signing environment variables are not set.");
}

const desktopConfigPath = path.join(__dirname, "..", "desktop-config.json");
if (fs.existsSync(desktopConfigPath)) {
  const desktopConfig = JSON.parse(fs.readFileSync(desktopConfigPath, "utf-8"));
  const apiUrl = String(process.env.API_URL || desktopConfig.apiUrl || "").trim();
  if (!apiUrl) {
    requiredForRelease.push("API_URL is not configured for desktop release.");
  } else if (/localhost|127\.0\.0\.1/i.test(apiUrl)) {
    requiredForRelease.push("Desktop release API URL still points to localhost.");
  }
}

if (allowInsecureRelease) {
  requiredForRelease.length = 0;
  warnings.push("ALLOW_INSECURE_DESKTOP_RELEASE=true bypassed strict release requirements.");
}

if (requiredForRelease.length > 0) {
  console.error("Desktop release check failed:");
  for (const item of requiredForRelease) {
    console.error(`- ${item}`);
  }
  process.exit(1);
}

console.log("Desktop release check passed.");
for (const item of warnings) {
  console.warn(`Warning: ${item}`);
}
