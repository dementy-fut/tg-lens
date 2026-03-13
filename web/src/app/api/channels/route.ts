import { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@/lib/supabase-server";

export async function GET() {
  const supabase = createServerClient();
  const { data } = await supabase.from("channels").select("*").order("category").order("title");
  return NextResponse.json(data || []);
}

export async function POST(req: NextRequest) {
  const body = await req.json();
  const supabase = createServerClient();

  const { data, error } = await supabase
    .from("channels")
    .upsert(
      {
        telegram_id: body.telegram_id,
        username: body.username,
        title: body.title,
        category: body.category || null,
        is_active: true,
      },
      { onConflict: "telegram_id" }
    )
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}

export async function PATCH(req: NextRequest) {
  const body = await req.json();
  const supabase = createServerClient();

  const update: Record<string, any> = {};
  if (body.is_active !== undefined) update.is_active = body.is_active;
  if (body.category !== undefined) update.category = body.category;

  const { data, error } = await supabase
    .from("channels")
    .update(update)
    .eq("id", body.id)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json(data);
}
