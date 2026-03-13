import { createServerClient } from "@/lib/supabase-server";
import { SummaryTimeline } from "@/components/summary-timeline";
import { Channel, ChannelSummary } from "@/lib/types";
import { notFound } from "next/navigation";
import Link from "next/link";

export const dynamic = "force-dynamic";

async function getChannel(id: string): Promise<Channel | null> {
  const supabase = createServerClient();
  const { data } = await supabase.from("channels").select("*").eq("id", id).single();
  return data;
}

async function getSummaries(channelId: string): Promise<ChannelSummary[]> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channel_summaries")
    .select("*")
    .eq("channel_id", channelId)
    .eq("status", "done")
    .order("period_end", { ascending: false })
    .limit(50);
  return data || [];
}

export default async function ChannelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const channel = await getChannel(id);
  if (!channel) notFound();

  const summaries = await getSummaries(channel.id);

  return (
    <main className="max-w-5xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Dashboard
      </Link>

      <div className="mb-6">
        <h1 className="text-2xl font-bold">{channel.title}</h1>
        <p className="text-gray-500">@{channel.username} &middot; {channel.category}</p>
      </div>

      <SummaryTimeline summaries={summaries} />
    </main>
  );
}
