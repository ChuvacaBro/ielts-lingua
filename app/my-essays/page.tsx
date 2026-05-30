"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Essays, type EssayRecord } from "@/lib/storage/local";

export default function MyEssaysPage() {
  const [items, setItems] = useState<EssayRecord[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    setItems(Essays.list());
  }, []);

  function exportTxt(rec: EssayRecord) {
    const text = `Writing Test ${rec.testId}\nSaved: ${rec.timestamp}\n\n=== Task 1 ===\n${rec.task1}\n\n=== Task 2 ===\n${rec.task2}\n`;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `essay-${rec.testId}-${rec.timestamp.replace(/[:.]/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function remove(rec: EssayRecord) {
    if (!confirm("Delete this essay?")) return;
    Essays.remove(rec.testId, rec.timestamp);
    setItems(Essays.list());
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-exam-accent text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">My Writing Essays</h1>
      {items.length === 0 ? (
        <p className="text-gray-600">No saved essays yet.</p>
      ) : (
        <ul className="divide-y divide-exam-border border border-exam-border">
          {items.map((rec) => {
            const key = `${rec.testId}-${rec.timestamp}`;
            return (
              <li key={key} className="p-3">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-mono">Test {rec.testId}</span>
                  <span className="text-gray-500">{new Date(rec.timestamp).toLocaleString()}</span>
                  <span className="text-gray-700">
                    T1: {rec.task1.split(/\s+/).filter(Boolean).length}w · T2:{" "}
                    {rec.task2.split(/\s+/).filter(Boolean).length}w
                  </span>
                  <button
                    className="ml-auto text-exam-accent"
                    onClick={() => setOpen(open === key ? null : key)}
                  >
                    {open === key ? "Hide" : "View"}
                  </button>
                  <button className="text-sm" onClick={() => exportTxt(rec)}>
                    Export .txt
                  </button>
                  <button className="text-red-700 text-sm" onClick={() => remove(rec)}>
                    Delete
                  </button>
                </div>
                {open === key && (
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <div className="font-semibold mb-1">Task 1</div>
                      <pre className="whitespace-pre-wrap font-exam">{rec.task1}</pre>
                    </div>
                    <div>
                      <div className="font-semibold mb-1">Task 2</div>
                      <pre className="whitespace-pre-wrap font-exam">{rec.task2}</pre>
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
