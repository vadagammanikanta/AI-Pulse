import { NextRequest, NextResponse } from "next/server";
import { generateAuthToken } from "@/lib/auth";

// In-memory sliding window rate limiter for failed login attempts
// Key: IP, Value: list of timestamp timestamps
const failedAttemptsMap = new Map<string, number[]>();

const MAX_FAILED_ATTEMPTS = 5;
const WINDOW_MS = 60 * 1000; // 1 minute

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const attempts = failedAttemptsMap.get(ip) || [];
  const recent = attempts.filter((t) => now - t < WINDOW_MS);
  failedAttemptsMap.set(ip, recent);
  return recent.length >= MAX_FAILED_ATTEMPTS;
}

function recordFailedAttempt(ip: string) {
  const attempts = failedAttemptsMap.get(ip) || [];
  attempts.push(Date.now());
  failedAttemptsMap.set(ip, attempts);
}

export async function POST(request: NextRequest) {
  const ip = request.headers.get("x-forwarded-for") || "127.0.0.1";

  if (isRateLimited(ip)) {
    return NextResponse.json(
      { error: "Too many failed login attempts. Please wait 60 seconds." },
      { status: 429 }
    );
  }

  const authPassword = process.env.AUTH_PASSWORD;
  const isProduction = process.env.NODE_ENV === "production";

  // In production, if AUTH_PASSWORD is not configured, refuse
  if (isProduction && !authPassword) {
    return NextResponse.json(
      { error: "AUTH_PASSWORD not set in environment." },
      { status: 500 }
    );
  }

  const { password } = await request.json();

  if (!authPassword || password === authPassword) {
    const token = await generateAuthToken(authPassword || password);
    const response = NextResponse.json({ success: true });
    response.cookies.set("auth_token", token, {
      httpOnly: true,
      secure: isProduction,
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 30, // 30 days
      path: "/",
    });
    return response;
  }

  recordFailedAttempt(ip);
  return NextResponse.json({ error: "Invalid password" }, { status: 401 });
}
