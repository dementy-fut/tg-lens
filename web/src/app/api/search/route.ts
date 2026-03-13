import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase-server";

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get("q");
  const channelId = req.nextUrl.searchParams.get("channel");
  const from = req.nextUrl.searchParams.get("from");
  const to = req.nextUrl.searchParams.get("to");

  if (!query) {
    return NextResponse.json({ error: "Query required" }, { status: 400 });
  }

  const supabase = createServerClient();

  let postsQuery = supabase
    .from("posts")
    .select("*, channels!inner(title, username, category)")
    .textSearch("text", query, { type: "websearch", config: "russian" })
    .order("date", { ascending: false })
    .limit(100);

  if (channelId) postsQuery = postsQuery.eq("channel_id", channelId);
  if (from) postsQuery = postsQuery.gte("date", from);
  if (to) postsQuery = postsQuery.lte("date", to);

  const { data: posts, error } = await postsQuery;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  let commentsQuery = supabase
    .from("comments")
    .select("*, posts!inner(id, link, channel_id)")
    .textSearch("text", query, { type: "websearch", config: "russian" })
    .order("date", { ascending: false })
    .limit(50);

  const { data: comments } = await commentsQuery;

  return NextResponse.json({ posts: posts || [], comments: comments || [] });
}
