"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Speaking, type SpeakingRecord } from "@/lib/storage/local";

export default function MySpeakingPage() {
  const [items, setItems] = useState<SpeakingRecord[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setItems(Speaking.list());
  }, []);

  function exportTxt(rec: SpeakingRecord) {
    const text = `Speaking Test ${rec.testId}\nSaved: ${rec.timestamp}\n\n=== Part 1 ===\n${rec.part1.join("\n\n")}\n\n=== Part 2 ===\n${rec.part2}\n\n=== Part 3 ===\n${rec.part3.join("\n\n")}\n`;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `speaking-${rec.testId}-${rec.timestamp.replace(/[:.]/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function remove(rec: SpeakingRecord) {
    if (!confirm("Delete this speaking answer set?")) return;
    Speaking.remove(rec.testId, rec.timestamp);
    setItems(Speaking.list());
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-exam-accent text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">My Speaking Answers</h1>
      {items.length === 0 ? (
        <p className="text-gray-600">No saved speaking answers yet.</p>
      ) : (
        <ul className="divide-y divide-exam-border border border-exam-border">
          {items.map((rec) => {
            const key = `${rec.testId}-${rec.timestamp}`;
            return (
              <li key={key} className="p-3">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-mono">Test {rec.testId}</span>
                  <span className="text-gray-500">{new Date(rec.timestamp).toLocaleString()}</span>
                  <button className="ml-auto text-exam-accent" onClick={() => setOpen(open === key ? null : key)}>
                    {open === key ? "Hide" : "View"}
                  </button>
                  <button onClick={() => exportTxt(rec)}>Export .txt</button>
                  <button className="text-red-700" onClick={() => remove(rec)}>
                    Delete
                  </button>
                </div>
                {open === key && (
                  <div className="mt-3 text-sm space-y-3">
                    <div>
                      <div className="font-semibold">Part 1</div>
                      <pre className="whitespace-pre-wrap font-exam">{rec.part1.join("\n\n")}</pre>
                    </div>
                    <div>
                      <div className="font-semibold">Part 2</div>
                      <pre className="whitespace-pre-wrap font-exam">{rec.part2}</pre>
                    </div>
                    <div>
                      <div className="font-semibold">Part 3</div>
                      <pre className="whitespace-pre-wrap font-exam">{rec.part3.join("\n\n")}</pre>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
