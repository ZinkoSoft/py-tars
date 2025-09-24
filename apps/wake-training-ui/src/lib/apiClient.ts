import axios from "axios";

const RAW_API_BASE_URL = __API_BASE_URL__ ?? "/api";
const ABSOLUTE_URL_PATTERN = /^https?:\/\//i;

export const API_BASE_URL = RAW_API_BASE_URL;

export const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10_000,
  headers: {
    "Content-Type": "application/json",
  },
});

function resolveApiBaseUrl(): URL | null {
  if (ABSOLUTE_URL_PATTERN.test(API_BASE_URL)) {
    return new URL(API_BASE_URL);
  }
  if (typeof window !== "undefined" && typeof window.location !== "undefined") {
    return new URL(API_BASE_URL, window.location.origin);
  }
  return null;
}

export function websocketUrl(path: string): string {
  const absolute = resolveApiBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (absolute) {
    const wsProtocol = absolute.protocol === "https:" ? "wss:" : "ws:";
    return `${wsProtocol}//${absolute.host}${normalizedPath}`;
  }

  const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
  const wsProtocol = isHttps ? "wss:" : "ws:";
  const host = typeof window !== "undefined" ? window.location.host : "localhost";
  return `${wsProtocol}//${host}${normalizedPath}`;
}
