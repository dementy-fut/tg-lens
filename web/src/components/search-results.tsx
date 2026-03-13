"use client";

import { format } from "date-fns";
import { ru } from "date-fns/locale";

interface SearchPost {
  id: string;
  text: string | null;
  date: string;
  views: number;
  link: string | null;
  channels: { title: string; username: string; category: string | null };
}

interface Props {
  posts: SearchPost[];
}

export function SearchResults({ posts }: Props) {
  if (posts.length === 0) {
    return <p className="text-gray-500 text-center py-8">Nothing found.</p>;
  }

  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <div key={post.id} className="border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-blue-600">
              {post.channels.title}
            </span>
            <span className="text-xs text-gray-400">
              {format(new Date(post.date), "d MMM yyyy", { locale: ru })}
            </span>
            {post.views > 0 && (
              <span className="text-xs text-gray-400">{post.views} views</span>
            )}
          </div>
          <p className="text-sm text-gray-800 whitespace-pre-wrap line-clamp-6">
            {post.text}
          </p>
          {post.link && (
            <a
              href={post.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-500 hover:underline mt-2 inline-block"
            >
              Open in Telegram
            </a>
          )}
        </div>
      ))}
    </div>
  );
}
