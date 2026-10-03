import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.FASTAPI_BACKEND_URL || "http://127.0.0.1:8000";
const API_SECRET_KEY = process.env.API_SECRET_KEY || "";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const targetUrl = `${BACKEND_URL}/items/${params.id}`;

  try {
    const res = await fetch(targetUrl, {
      headers: {
        "X-API-Key": API_SECRET_KEY,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    if (!res.ok) {
      return NextResponse.json(
        { error: `Backend returned status ${res.status}` },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to fetch item detail", detail: err.message },
      { status: 502 }
    );
  }
}
