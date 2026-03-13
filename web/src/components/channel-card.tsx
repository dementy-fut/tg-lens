import Link from "next/link";
import { Channel } from "@/lib/types";
import { formatDistanceToNow } from "date-fns";
import { ru } from "date-fns/locale";

interface Props {
  channel: Channel;
  latestSummary?: string;
}

export function ChannelCard({ channel, latestSummary }: Props) {
  return (
    <Link href={`/channels/${channel.id}`}>
      <div className="border rounded-lg p-4 hover:border-blue-400 hover:shadow-sm transition-all">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900">{channel.title}</h3>
          {channel.category && (
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
              {channel.category}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500 mb-2">
          @{channel.username}
          {channel.last_scraped_at && (
            <> &middot; updated {formatDistanceToNow(new Date(channel.last_scraped_at), { addSuffix: true, locale: ru })}</>
          )}
        </p>
        {latestSummary && (
          <p className="text-sm text-gray-700 line-clamp-3">{latestSummary}</p>
        )}
      </div>
    </Link>
  );
}
