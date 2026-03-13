"use client";

import { useState } from "react";

export function ScrapeButton() {
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");

  async function handleScrape() {
    setStatus("loading");
    try {
      const res = await fetch("/api/trigger-scrape", { method: "POST" });
      if (res.ok || res.redirected) {
        setStatus("done");
        setTimeout(() => setStatus("idle"), 3000);
      } else {
        setStatus("error");
        setTimeout(() => setStatus("idle"), 3000);
      }
    } catch {
      setStatus("error");
      setTimeout(() => setStatus("idle"), 3000);
    }
  }

  return (
    <button
      onClick={handleScrape}
      disabled={status === "loading"}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
        status === "done"
          ? "bg-green-600 text-white"
          : status === "error"
          ? "bg-red-600 text-white"
          : "bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
      }`}
    >
      {status === "loading" && "Starting..."}
      {status === "done" && "Scrape started!"}
      {status === "error" && "Error"}
      {status === "idle" && "Scrape Now"}
    </button>
  );
}
