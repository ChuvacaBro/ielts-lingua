"use client";

import { formatMMSS } from "./useExamTimer";

export function TopTimer({
  remaining,
  label,
  warn,
  prefix,
}: {
  remaining: number;
  label: string;
  warn?: boolean;
  prefix?: string;
}) {
  return (
    <div className="sticky top-0 z-50 w-full border-b border-exam-border bg-white py-2 px-4 flex items-center justify-between">
      <div className="text-sm text-gray-600">{label}</div>
      <div
        className={
          "font-mono text-2xl tabular-nums " + (warn ? "text-exam-warn" : "text-exam-text")
        }
      >
        {prefix && <span className="text-sm mr-1">{prefix}</span>}
        {formatMMSS(remaining)}
      </div>
    </div>
  );
}
