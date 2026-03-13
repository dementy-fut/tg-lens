import { createServerClient } from "@/lib/supabase-server";
import { ChannelCard } from "@/components/channel-card";
import { Channel, ChannelSummary } from "@/lib/types";
import Link from "next/link";
import { ScrapeButton } from "@/components/scrape-button";

export const dynamic = "force-dynamic";

async function getChannels(): Promise<Channel[]> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channels")
    .select("*")
    .eq("is_active", true)
    .order("category")
    .order("title");
  return data || [];
}

async function getLatestDigests(): Promise<Record<string, ChannelSummary>> {
  const supabase = createServerClient();
  const { data } = await supabase
    .from("channel_summaries")
    .select("*")
    .eq("status", "done")
    .order("period_end", { ascending: false });

  const map: Record<string, ChannelSummary> = {};
  for (const s of data || []) {
    if (!map[s.channel_id]) {
      map[s.channel_id] = s;
    }
  }
  return map;
}

export default async function Dashboard() {
  const [channels, digests] = await Promise.all([getChannels(), getLatestDigests()]);

  const grouped: Record<string, Channel[]> = {};
  for (const ch of channels) {
    const cat = ch.category || "other";
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(ch);
  }

  return (
    <main className="max-w-5xl mx-auto p-6">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">TG Lens</h1>
        <div className="flex gap-2">
          <Link href="/search" className="text-sm text-gray-600 hover:text-gray-900 px-3 py-2">Search</Link>
          <Link href="/settings" className="text-sm text-gray-600 hover:text-gray-900 px-3 py-2">Settings</Link>
          <ScrapeButton />
        </div>
      </div>

      {Object.keys(grouped).length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p>No channels yet. <Link href="/settings" className="text-blue-600 hover:underline">Add channels</Link> to get started.</p>
        </div>
      )}

      {Object.entries(grouped).map(([category, chs]) => (
        <section key={category} className="mb-8">
          <h2 className="text-lg font-semibold text-gray-700 mb-3 capitalize">{category}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {chs.map((ch) => (
              <ChannelCard
                key={ch.id}
                channel={ch}
                latestSummary={digests[ch.id]?.summary?.slice(0, 200)}
              />
            ))}
          </div>
        </section>
      ))}
    </main>
  );
}
