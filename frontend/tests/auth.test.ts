import { describe, expect, it } from "vitest";
import { isProtectedRoute, isPublicRoute } from "../lib/auth";

describe("route access", () => {
  it("treats landing and auth pages as public", () => {
    expect(isPublicRoute("/")).toBe(true);
    expect(isPublicRoute("/login")).toBe(true);
    expect(isPublicRoute("/register")).toBe(true);
  });

  it("protects every feature route", () => {
    for (const p of ["/dashboard", "/board", "/communicate/1", "/history", "/learn", "/vocabulary", "/settings", "/onboarding"]) {
      expect(isProtectedRoute(p)).toBe(true);
    }
  });

  it("ignores trailing slashes and query strings", () => {
    expect(isPublicRoute("/login/")).toBe(true);
    expect(isProtectedRoute("/dashboard?fresh=1")).toBe(true);
  });
});
