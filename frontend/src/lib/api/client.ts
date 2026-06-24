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

function readWindowNameToken() {
  if (typeof window === "undefined") {
    return null;
  }

  const prefix = "auth_token:";
  return window.name.startsWith(prefix) ? window.name.slice(prefix.length) : null;
}

function readStoredToken() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage?.getItem(ACCESS_TOKEN_STORAGE_KEY) || null;
  } catch {
    return null;
  }
}

function storeAccessToken(token: string) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.localStorage?.setItem(ACCESS_TOKEN_STORAGE_KEY, token);
  } catch {
    // Ignore storage failures in restricted browser environments.
  }

  window.name = `auth_token:${token}`;
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
  },
});

apiClient.interceptors.request.use((config) => {
  const bearerToken = readStoredToken() || readCookie("access_token") || readCookie("auth_token") || readWindowNameToken();

  if (bearerToken) {
    config.headers.Authorization = `Bearer ${bearerToken}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => {
    const accessToken = response.data?.access_token;

    if (typeof accessToken === "string" && accessToken.length > 0) {
      storeAccessToken(accessToken);
    }

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

export default apiClient;
export { clearStoredAccessToken };
