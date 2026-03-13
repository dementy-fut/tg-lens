"use client";

import { useState } from "react";
import { SearchResults } from "@/components/search-results";
import Link from "next/link";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ posts: any[]; comments: any[] } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      setResults(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-blue-600 text-sm hover:underline mb-4 block">
        &larr; Dashboard
      </Link>

      <h1 className="text-2xl font-bold mb-6">Search</h1>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search messages..."
            className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "..." : "Search"}
          </button>
        </div>
      </form>

      {results && (
        <>
          <p className="text-sm text-gray-500 mb-4">
            Found {results.posts.length} posts, {results.comments.length} comments
          </p>
          <SearchResults posts={results.posts} />
        </>
      )}
    </main>
  );
}
