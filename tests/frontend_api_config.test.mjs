import assert from "node:assert/strict";
import test from "node:test";
import { resolveApiBaseUrl } from "../assets/js/api-config.mjs";

test("local development retains the Flask API on port 5000", () => {
  assert.equal(
    resolveApiBaseUrl("", "http://127.0.0.1:8000"),
    "http://127.0.0.1:5000/api",
  );
  assert.equal(
    resolveApiBaseUrl("", "http://localhost:8000"),
    "http://localhost:5000/api",
  );
  assert.equal(
    resolveApiBaseUrl("", "http://[::1]:8000"),
    "http://[::1]:5000/api",
  );
});

test("production defaults to the same-origin HTTPS API", () => {
  assert.equal(
    resolveApiBaseUrl("", "https://app.example.test"),
    "https://app.example.test/api",
  );
});

test("production accepts a configured HTTPS API base", () => {
  assert.equal(
    resolveApiBaseUrl("https://api.example.test", "https://app.example.test"),
    "https://api.example.test/api",
  );
});

test("configured backend paths and credentials are handled safely", () => {
  assert.equal(
    resolveApiBaseUrl("https://api.example.test/platform/", "https://app.example.test"),
    "https://api.example.test/platform/api",
  );
  assert.throws(
    () => resolveApiBaseUrl("https://user:password@api.example.test", "https://app.example.test"),
    /must not be embedded/,
  );
});

test("an HTTPS frontend rejects an insecure configured API", () => {
  assert.throws(
    () => resolveApiBaseUrl("http://api.example.test", "https://app.example.test"),
    /requires an HTTPS API URL/,
  );
});

test("a configured API base must be an absolute HTTP URL", () => {
  assert.throws(
    () => resolveApiBaseUrl("//api.example.test", "http://localhost:8000"),
    TypeError,
  );
});
