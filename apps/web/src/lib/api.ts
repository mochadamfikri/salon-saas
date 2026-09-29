export type ApiConnectivityResult =
  | { status: "connected" }
  | { status: "unavailable"; message: string };

export async function checkApiConnectivity(
  apiBaseUrl: string,
  fetcher: typeof fetch = fetch,
): Promise<ApiConnectivityResult> {
  try {
    const response = await fetcher(`${apiBaseUrl}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return { status: "unavailable", message: `API returned ${response.status}` };
    }

    const payload: unknown = await response.json();
    if (
      typeof payload === "object" &&
      payload !== null &&
      "status" in payload &&
      payload.status === "ok"
    ) {
      return { status: "connected" };
    }

    return { status: "unavailable", message: "API returned an unexpected response" };
  } catch {
    return { status: "unavailable", message: "API is unavailable" };
  }
}
