import { NextRequest, NextResponse } from "next/server";
import { generateAuthToken } from "@/lib/auth";

export async function middleware(request: NextRequest) {
  const authPassword = process.env.AUTH_PASSWORD;
  const isProduction = process.env.NODE_ENV === "production";
  const pathname = request.nextUrl.pathname;

  // Fail-Closed Rule: In production, if AUTH_PASSWORD is not set, refuse to serve!
  if (isProduction && !authPassword) {
    if (pathname.startsWith('/api/')) {
      return NextResponse.json(
        { error: "AUTH_PASSWORD environment variable must be set in production mode. Refusing unauthenticated access." },
        { status: 500 }
      );
    }
    return new NextResponse(
      "<h1>500 Internal Server Error</h1><p>AUTH_PASSWORD environment variable must be set in production mode.</p>",
      { status: 500, headers: { "content-type": "text/html" } }
    );
  }

  // Bypassed in development mode ONLY if no AUTH_PASSWORD configured
  if (!isProduction && !authPassword) {
    return NextResponse.next();
  }

  // Always exclude login page, login API, static assets, PWA manifest, and service worker
  if (
    pathname === '/login' ||
    pathname.startsWith('/api/auth/login') ||
    pathname.startsWith('/_next') ||
    pathname.startsWith('/manifest.json') ||
    pathname.startsWith('/sw.js') ||
    pathname.startsWith('/favicon.ico')
  ) {
    return NextResponse.next();
  }

  const expectedToken = await generateAuthToken(authPassword || "");
  const cookieToken = request.cookies.get("auth_token")?.value;

  if (!cookieToken || cookieToken !== expectedToken) {
    if (pathname.startsWith('/api/')) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const loginUrl = new URL('/login', request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
