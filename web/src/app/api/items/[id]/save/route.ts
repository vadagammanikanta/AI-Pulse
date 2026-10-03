import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.FASTAPI_BACKEND_URL || "http://127.0.0.1:8000";
const API_SECRET_KEY = process.env.API_SECRET_KEY || "";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const targetUrl = `${BACKEND_URL}/items/${params.id}/save`;

  try {
    const res = await fetch(targetUrl, {
      method: "POST",
      headers: {
        "X-API-Key": API_SECRET_KEY,
        "Content-Type": "application/json",
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to save item", detail: err.message },
      { status: 502 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const targetUrl = `${BACKEND_URL}/items/${params.id}/save`;

  try {
    const res = await fetch(targetUrl, {
      method: "DELETE",
      headers: {
        "X-API-Key": API_SECRET_KEY,
        "Content-Type": "application/json",
      },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      { error: "Failed to unsave item", detail: err.message },
      { status: 502 }
    );
  }
}
