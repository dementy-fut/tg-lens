export interface Channel {
  id: string;
  telegram_id: number;
  username: string;
  title: string;
  category: string | null;
  is_active: boolean;
  last_scraped_at: string | null;
  created_at: string;
}

export interface Post {
  id: string;
  channel_id: string;
  telegram_msg_id: number;
  text: string | null;
  date: string;
  views: number;
  forwards: number;
  reactions_json: Record<string, number> | null;
  has_media: boolean;
  media_type: string | null;
  link: string | null;
}

export interface Comment {
  id: string;
  post_id: string;
  telegram_msg_id: number;
  sender_name: string | null;
  sender_id: number | null;
  text: string | null;
  date: string;
  is_reply: boolean;
}

export interface ChannelSummary {
  id: string;
  channel_id: string;
  period_type: string;
  period_start: string;
  period_end: string;
  summary: string | null;
  facts_json: Record<string, string> | null;
  post_count: number | null;
  status: string;
  created_at: string;
}

export type DigestFormat = "headlines" | "brief" | "deep" | "qa" | "actions";

export const DIGEST_FORMAT_LABELS: Record<DigestFormat, string> = {
  headlines: "Headlines",
  brief: "Brief",
  deep: "Deep Dive",
  qa: "Q&A",
  actions: "Actions",
};
