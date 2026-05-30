"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Attempts, type AttemptRecord } from "@/lib/storage/local";

export default function HistoryPage() {
  const [items, setItems] = useState<AttemptRecord[]>([]);
  useEffect(() => {
    setItems(Attempts.list());
  }, []);
  return (
    <div className="max-w-4xl mx-auto p-6">
      <Link href="/" className="text-exam-accent text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">Attempt History</h1>
      {items.length === 0 ? (
        <p className="text-gray-600">No attempts yet.</p>
      ) : (
        <table className="w-full text-sm border border-exam-border">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-2 py-1 border-b border-exam-border">Section</th>
              <th className="text-left px-2 py-1 border-b border-exam-border">Test</th>
              <th className="text-left px-2 py-1 border-b border-exam-border">Started</th>
              <th className="text-left px-2 py-1 border-b border-exam-border">Raw</th>
              <th className="text-left px-2 py-1 border-b border-exam-border">Band</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} className="border-b border-exam-border last:border-0">
                <td className="px-2 py-1">{a.section}</td>
                <td className="px-2 py-1 font-mono">{a.testId}</td>
                <td className="px-2 py-1">{new Date(a.startedAt).toLocaleString()}</td>
                <td className="px-2 py-1 font-mono">{a.raw ?? "—"}/{a.total ?? "—"}</td>
                <td className="px-2 py-1 font-mono">{a.band ?? "—"}</td>
                <td className="px-2 py-1">
                  <Link
                    href={`/results?id=${a.id}`}
                    className="text-exam-accent"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
