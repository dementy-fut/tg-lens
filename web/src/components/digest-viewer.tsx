"use client";

import { useState } from "react";
import { ChannelSummary, DigestFormat } from "@/lib/types";
import { FormatSwitcher } from "./format-switcher";

interface Props {
  summary: ChannelSummary;
}

export function DigestViewer({ summary }: Props) {
  const [format, setFormat] = useState<DigestFormat>("brief");
  const content = summary.facts_json?.[format] || summary.summary || "No digest available.";

  return (
    <div>
      <FormatSwitcher current={format} onChange={setFormat} />
      <div className="mt-4 prose prose-sm max-w-none whitespace-pre-wrap">
        {content}
      </div>
    </div>
  );
}
