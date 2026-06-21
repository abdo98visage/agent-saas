#!/usr/bin/env node
"use strict";

const requiredForRelease = [];
const warnings = [];

const updateFeedUrl = process.env.UPDATE_FEED_URL || "";
if (!updateFeedUrl) {
  warnings.push("UPDATE_FEED_URL is not set. Auto-update will remain unconfigured.");
}

const hasWindowsSigning =
  Boolean(process.env.CSC_LINK && process.env.CSC_KEY_PASSWORD) ||
  Boolean(process.env.WIN_CSC_LINK && process.env.WIN_CSC_KEY_PASSWORD);

if (!hasWindowsSigning) {
  warnings.push("Windows code-signing environment variables are not set. The EXE will build unsigned.");
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
