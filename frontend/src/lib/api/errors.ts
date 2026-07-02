export interface ApiError {
  response?: {
    data?: {
      detail?: unknown;
    };
  };
}

export function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "response" in error) {
    const apiError = error as ApiError;
    const detail = apiError.response?.data?.detail;

    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item !== null && "msg" in item && typeof item.msg === "string"
            ? item.msg
            : String(item),
        )
        .join(", ") || fallback;
    }
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
