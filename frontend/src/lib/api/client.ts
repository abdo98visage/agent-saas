import axios from "axios";

const ACCESS_TOKEN_STORAGE_KEY = "admin-access-token";

function readCookie(name: string) {
  if (typeof document === "undefined") {
    return null;
  }

  const prefix = `${name}=`;
  const match = document.cookie
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));

  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

function clearStoredAccessToken() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage?.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  } catch {
    // Ignore storage failures in restricted browser environments.
  }

  if (window.name.startsWith("auth_token:")) {
    window.name = "";
  }
}

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
    "X-Client-Type": "browser",
  },
});

apiClient.interceptors.request.use((config) => {
  const method = String(config.method || "get").toLowerCase();
  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrfToken = readCookie("csrf_token");
    if (csrfToken) {
      config.headers["X-CSRF-Token"] = csrfToken;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    if (response.config.url?.includes("/auth/logout")) {
      clearStoredAccessToken();
    }

    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      clearStoredAccessToken();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Remove tokens left by versions that exposed browser JWTs to JavaScript.
clearStoredAccessToken();

export default apiClient;
export { clearStoredAccessToken };
