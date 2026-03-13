import { NextResponse } from "next/server";

export async function POST() {
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPO || "dementy-fut/tg-lens";

  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not set" }, { status: 500 });
  }

  const res = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/scrape.yml/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github.v3+json",
      },
      body: JSON.stringify({ ref: "master" }),
    }
  );

  if (res.ok || res.status === 204) {
    return NextResponse.json({ ok: true });
  }

  const error = await res.text();
  return NextResponse.json({ error }, { status: res.status });
}
