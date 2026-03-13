"use client";

import { useEffect, useState } from "react";
import { Channel } from "@/lib/types";
import Link from "next/link";

export default function SettingsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [newChannel, setNewChannel] = useState({ telegram_id: "", username: "", title: "", category: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch("/api/channels").then((r) => r.json()).then(setChannels);
  }, []);

  async function addChannel(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch("/api/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...newChannel, telegram_id: parseInt(newChannel.telegram_id) }),
      });
      if (res.ok) {
        const ch = await res.json();
        setChannels((prev) => [...prev, ch]);
        setNewChannel({ telegram_id: "", username: "", title: "", category: "" });
      }
    } finally {
      setSaving(false);
    }
  }

  async function toggleChannel(ch: Channel) {
    const res = await fetch("/api/channels", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: ch.id, is_active: !ch.is_active }),
    });
    if (res.ok) {
      setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: !c.is_active } : c)));
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">&larr; Dashboard</Link>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <form onSubmit={addChannel} className="border rounded-lg p-4 mb-6 space-y-3">
        <h2 className="font-semibold">Add Channel</h2>
        <div className="grid grid-cols-2 gap-3">
          <input placeholder="Telegram ID" value={newChannel.telegram_id} onChange={(e) => setNewChannel((p) => ({ ...p, telegram_id: e.target.value }))} className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="@username" value={newChannel.username} onChange={(e) => setNewChannel((p) => ({ ...p, username: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
          <input placeholder="Title" value={newChannel.title} onChange={(e) => setNewChannel((p) => ({ ...p, title: e.target.value }))} className="border rounded px-3 py-2 text-sm" required />
          <input placeholder="Category (tech, offroad, news...)" value={newChannel.category} onChange={(e) => setNewChannel((p) => ({ ...p, category: e.target.value }))} className="border rounded px-3 py-2 text-sm" />
        </div>
        <button type="submit" disabled={saving} className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50">
          {saving ? "Adding..." : "Add"}
        </button>
      </form>

      <h2 className="font-semibold mb-3">Channels ({channels.length})</h2>
      <div className="space-y-2">
        {channels.map((ch) => (
          <div key={ch.id} className="flex items-center justify-between border rounded-lg px-4 py-3">
            <div>
              <span className="font-medium">{ch.title}</span>
              <span className="text-gray-500 text-sm ml-2">@{ch.username}</span>
              {ch.category && <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full ml-2">{ch.category}</span>}
            </div>
            <button onClick={() => toggleChannel(ch)} className={`text-sm px-3 py-1 rounded ${ch.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
              {ch.is_active ? "Active" : "Disabled"}
            </button>
          </div>
        ))}
      </div>
    </main>
  );
}
