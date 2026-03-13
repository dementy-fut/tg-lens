"use client";

import { useState } from "react";
import { ChannelSummary, DigestFormat } from "@/lib/types";
import { FormatSwitcher } from "./format-switcher";
import { format } from "date-fns";
import { ru } from "date-fns/locale";

interface Props {
  summaries: ChannelSummary[];
}

export function SummaryTimeline({ summaries }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(summaries[0]?.id || null);
  const [digestFormat, setDigestFormat] = useState<DigestFormat>("brief");

  const selected = summaries.find((s) => s.id === selectedId);
  const content = selected?.facts_json?.[digestFormat] || selected?.summary || "";

  return (
    <div className="grid grid-cols-4 gap-6">
      <div className="col-span-1 space-y-1 max-h-[600px] overflow-y-auto">
        {summaries.map((s) => (
          <button
            key={s.id}
            onClick={() => setSelectedId(s.id)}
            className={`w-full text-left px-3 py-2 rounded-md text-sm ${
              selectedId === s.id
                ? "bg-blue-50 text-blue-700 font-medium"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            <div>{s.period_type}</div>
            <div className="text-xs text-gray-400">
              {format(new Date(s.period_start), "d MMM", { locale: ru })} —{" "}
              {format(new Date(s.period_end), "d MMM yyyy", { locale: ru })}
            </div>
          </button>
        ))}
      </div>

      <div className="col-span-3">
        {selected ? (
          <>
            <FormatSwitcher current={digestFormat} onChange={setDigestFormat} />
            <div className="mt-4 prose prose-sm max-w-none whitespace-pre-wrap">
              {content}
            </div>
            {selected.post_count && (
              <p className="mt-4 text-xs text-gray-400">
                {selected.post_count} posts analyzed
              </p>
            )}
          </>
        ) : (
          <p className="text-gray-500">No digests yet. Run the pipeline first.</p>
        )}
      </div>
    </div>
  );
}
