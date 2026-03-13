"use client";

import { DigestFormat, DIGEST_FORMAT_LABELS } from "@/lib/types";

interface Props {
  current: DigestFormat;
  onChange: (format: DigestFormat) => void;
}

const FORMATS: DigestFormat[] = ["headlines", "brief", "deep", "qa", "actions"];

export function FormatSwitcher({ current, onChange }: Props) {
  return (
    <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
      {FORMATS.map((fmt) => (
        <button
          key={fmt}
          onClick={() => onChange(fmt)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            current === fmt
              ? "bg-white shadow-sm text-gray-900"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          {DIGEST_FORMAT_LABELS[fmt]}
        </button>
      ))}
    </div>
  );
}
