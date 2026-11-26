const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function resolveApiBaseUrl(configuredBase, pageOrigin) {
  const origin = new URL(pageOrigin);
  const configured = configuredBase?.trim();
  if (configured) {
    const apiUrl = new URL(configured);
    if (!["http:", "https:"].includes(apiUrl.protocol)) {
      throw new Error("The AgriLearn API URL must use HTTP or HTTPS.");
    }
    if (origin.protocol === "https:" && apiUrl.protocol !== "https:") {
      throw new Error("An HTTPS AgriLearn frontend requires an HTTPS API URL.");
    }
    if (apiUrl.username || apiUrl.password) {
      throw new Error("Credentials must not be embedded in the AgriLearn API URL.");
    }
    const basePath = apiUrl.pathname.replace(/\/+$/, "");
    apiUrl.pathname = !basePath
      ? "/api"
      : basePath.endsWith("/api")
        ? basePath
        : `${basePath}/api`;
    apiUrl.search = "";
    apiUrl.hash = "";
    return apiUrl.toString().replace(/\/$/, "");
  }

  if (LOCAL_HOSTS.has(origin.hostname)) {
    origin.port = "5000";
    origin.pathname = "/api";
    origin.search = "";
    origin.hash = "";
    return origin.toString().replace(/\/$/, "");
  }
  return new URL("/api", origin).toString().replace(/\/$/, "");
}
