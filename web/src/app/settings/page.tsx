"use client";

import { useEffect, useState } from "react";
import { Channel } from "@/lib/types";
import Link from "next/link";

export default function SettingsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "active" | "disabled">("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/channels")
      .then((r) => r.json())
      .then((data) => { setChannels(data); setLoading(false); });
  }, []);

  async function toggleChannel(ch: Channel) {
    // Optimistic update
    setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: !c.is_active } : c)));

    const res = await fetch("/api/channels", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: ch.id, is_active: !ch.is_active }),
    });
    if (!res.ok) {
      // Revert on error
      setChannels((prev) => prev.map((c) => (c.id === ch.id ? { ...c, is_active: ch.is_active } : c)));
    }
  }

  async function enableAll() {
    const filtered = getFiltered();
    const ids = filtered.filter((c) => !c.is_active).map((c) => c.id);
    if (!ids.length) return;

    setChannels((prev) => prev.map((c) => (ids.includes(c.id) ? { ...c, is_active: true } : c)));
    for (const id of ids) {
      await fetch("/api/channels", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, is_active: true }),
      });
    }
  }

  async function disableAll() {
    const filtered = getFiltered();
    const ids = filtered.filter((c) => c.is_active).map((c) => c.id);
    if (!ids.length) return;

    setChannels((prev) => prev.map((c) => (ids.includes(c.id) ? { ...c, is_active: false } : c)));
    for (const id of ids) {
      await fetch("/api/channels", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, is_active: false }),
      });
    }
  }

  function getFiltered() {
    return channels.filter((ch) => {
      const matchesSearch = !search ||
        ch.title.toLowerCase().includes(search.toLowerCase()) ||
        (ch.username && ch.username.toLowerCase().includes(search.toLowerCase()));
      const matchesFilter = filter === "all" || (filter === "active" ? ch.is_active : !ch.is_active);
      return matchesSearch && matchesFilter;
    });
  }

  const filtered = getFiltered();
  const activeCount = channels.filter((c) => c.is_active).length;

  return (
    <main className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">&larr; Dashboard</Link>
      <h1 className="text-2xl font-bold mb-2">Channels</h1>
      <p className="text-gray-500 text-sm mb-6">
        {activeCount} active / {channels.length} total. Click on a channel to toggle.
      </p>

      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search channels..."
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as "all" | "active" | "disabled")}
          className="border rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="all">All</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
      </div>

      <div className="flex gap-2 mb-4">
        <button
          onClick={enableAll}
          className="text-xs px-3 py-1.5 rounded bg-green-50 text-green-700 hover:bg-green-100 border border-green-200"
        >
          Enable shown ({filtered.filter((c) => !c.is_active).length})
        </button>
        <button
          onClick={disableAll}
          className="text-xs px-3 py-1.5 rounded bg-red-50 text-red-700 hover:bg-red-100 border border-red-200"
        >
          Disable shown ({filtered.filter((c) => c.is_active).length})
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {filtered.map((ch) => (
            <button
              key={ch.id}
              onClick={() => toggleChannel(ch)}
              className={`text-left rounded-lg px-4 py-3 border-2 transition-colors ${
                ch.is_active
                  ? "border-green-400 bg-green-50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`font-medium text-sm ${ch.is_active ? "text-green-800" : "text-gray-700"}`}>
                  {ch.title}
                </span>
                <span className={`w-3 h-3 rounded-full flex-shrink-0 ml-2 ${ch.is_active ? "bg-green-500" : "bg-gray-300"}`} />
              </div>
              {ch.username && (
                <span className="text-gray-400 text-xs">@{ch.username}</span>
              )}
              {ch.category && (
                <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full ml-2">{ch.category}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </main>
  );
}
