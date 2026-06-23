"use client";

const RIYADH_TIME_ZONE = "Asia/Riyadh";

const riyadhDateTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: RIYADH_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
});

const riyadhDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: RIYADH_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function formatRiyadhDateTime(value: string | number | Date) {
  return `${riyadhDateTimeFormatter.format(new Date(value))} GMT+3`;
}

export function formatRiyadhDateKey(value: string | number | Date) {
  return riyadhDateFormatter.format(new Date(value));
}
