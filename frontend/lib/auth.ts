// Central route-access rule: only the landing page and auth pages are public.
// Everything else requires a logged-in user (see RequireAuth).
const PUBLIC_ROUTES = ["/", "/login", "/register"];

function normalize(pathname: string): string {
  const path = pathname.split("?")[0].split("#")[0].replace(/\/+$/, "");
  return path === "" ? "/" : path;
}

export function isPublicRoute(pathname: string): boolean {
  return PUBLIC_ROUTES.includes(normalize(pathname));
}

export function isProtectedRoute(pathname: string): boolean {
  return !isPublicRoute(pathname);
}
