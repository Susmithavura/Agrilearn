import assert from "node:assert/strict";
import test from "node:test";

const requests = [];
globalThis.window = { location: { origin: "https://frontend.example.test" } };
globalThis.document = {
  querySelector: (selector) => selector === 'meta[name="agrilearn-api-base"]'
    ? { content: "https://api.example.test/service" }
    : null,
};
globalThis.fetch = async (input, options = {}) => {
  const url = new URL(input);
  requests.push({ url: url.toString(), options });
  if (url.pathname === "/service/api/auth/csrf") {
    return new Response(JSON.stringify({ data: { csrf_token: "bootstrap-csrf-token" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  if (url.pathname === "/service/api/auth/login") {
    return new Response(JSON.stringify({
      data: {
        user: { id: "1", role: "farmer" },
        csrf_token: "authenticated-csrf-token",
      },
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  if (url.pathname === "/service/api/sessions") {
    return new Response(JSON.stringify({ data: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  if (url.pathname === "/service/api/attendance") {
    return new Response(JSON.stringify({ data: { saved: true } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }
  throw new Error(`Unexpected API request: ${url.pathname}`);
};

const { API_CONFIG, apiRequest } = await import("../assets/js/api.js");

test("configured HTTPS API supports CSRF bootstrap, login, and session requests", async () => {
  assert.equal(API_CONFIG.baseUrl, "https://api.example.test/service/api");

  const login = await apiRequest("/auth/login", {
    method: "POST",
    body: { username: "demo.farmer", password: "test-only" },
  });
  assert.equal(login.user.role, "farmer");

  const sessions = await apiRequest("/sessions");
  assert.deepEqual(sessions, []);
  const attendance = await apiRequest("/attendance", {
    method: "POST",
    body: { records: [] },
  });
  assert.deepEqual(attendance, { saved: true });
  assert.deepEqual(
    requests.map(({ url }) => new URL(url).pathname),
    [
      "/service/api/auth/csrf",
      "/service/api/auth/login",
      "/service/api/sessions",
      "/service/api/attendance",
    ],
  );
  assert.ok(requests.every(({ url, options }) => (
    url.startsWith("https://api.example.test/")
      && options.credentials === "include"
  )));
  assert.equal(requests[1].options.headers["X-CSRF-Token"], "bootstrap-csrf-token");
  assert.equal(requests[3].options.headers["X-CSRF-Token"], "authenticated-csrf-token");
});
