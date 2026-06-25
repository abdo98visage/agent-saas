#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const requiredForRelease = [];
const warnings = [];
const allowInsecureRelease = process.env.ALLOW_INSECURE_DESKTOP_RELEASE === "true";
const releasePlatform = String(
  process.env.DESKTOP_RELEASE_PLATFORM ||
  process.env.npm_config_platform ||
  process.platform
).toLowerCase();

const updateFeedUrl = process.env.UPDATE_FEED_URL || "";
if (!updateFeedUrl) {
  requiredForRelease.push("UPDATE_FEED_URL is not set.");
}

const hasWindowsSigning =
  Boolean(process.env.CSC_LINK && process.env.CSC_KEY_PASSWORD) ||
  Boolean(process.env.WIN_CSC_LINK && process.env.WIN_CSC_KEY_PASSWORD);
const hasMacSigning =
  Boolean(process.env.CSC_LINK && process.env.CSC_KEY_PASSWORD) ||
  Boolean(process.env.CSC_NAME) ||
  Boolean(process.env.APPLE_API_KEY && process.env.APPLE_API_KEY_ID && process.env.APPLE_API_ISSUER);

if (releasePlatform === "win32" || releasePlatform === "windows") {
  if (!hasWindowsSigning) {
    requiredForRelease.push("Windows code-signing environment variables are not set.");
  }
} else if (releasePlatform === "darwin" || releasePlatform === "mac" || releasePlatform === "macos") {
  if (!hasMacSigning) {
    requiredForRelease.push("macOS signing or notarization environment variables are not set.");
  }
} else {
  warnings.push(`No platform-specific signing checks are defined for '${releasePlatform}'.`);
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
