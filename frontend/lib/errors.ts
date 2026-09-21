export function getErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error && typeof error === "object" && "response" in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}
