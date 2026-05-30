"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { Attempts, type AttemptRecord } from "@/lib/storage/local";

function ResultsContent() {
  const searchParams = useSearchParams();
  const attemptId = searchParams.get("id") || "";
  const [rec, setRec] = useState<AttemptRecord | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});

  useEffect(() => {
    const r = Attempts.list().find((a) => a.id === attemptId) || null;
    setRec(r);
    setAnswers(Attempts.getAnswers(attemptId));
  }, [attemptId]);

  if (!rec) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <p>No attempt found for this ID.</p>
        <Link href="/" className="text-exam-accent">
          ← Home
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <Link href="/" className="text-exam-accent text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">
        Results — {rec.section} test {rec.testId}
      </h1>
      <div className="border border-exam-border p-4 text-center mb-6">
        <div className="text-sm text-gray-600">Raw score</div>
        <div className="text-3xl font-mono">
          {rec.raw} / {rec.total}
        </div>
        <div className="text-sm text-gray-600 mt-3">Band score</div>
        <div className="text-4xl font-mono text-exam-accent">{rec.band}</div>
      </div>
      <div className="text-sm text-gray-600">
        Started: {new Date(rec.startedAt).toLocaleString()}
        <br />
        Finished:{" "}
        {rec.finishedAt ? new Date(rec.finishedAt).toLocaleString() : "—"}
      </div>
      <div className="mt-6 flex gap-2 text-sm">
        <Link href={`/${rec.section}/${rec.testId}`} className="border px-3 py-1">
          Retake same test
        </Link>
        <Link href={`/${rec.section}/${rec.testId}?review=1`} className="border px-3 py-1">
          Review answers (in section page)
        </Link>
      </div>
      <details className="mt-6 text-sm">
        <summary className="cursor-pointer text-exam-accent">
          Your raw answers ({Object.keys(answers).length})
        </summary>
        <pre className="bg-gray-50 p-3 mt-2 overflow-auto">
          {JSON.stringify(answers, null, 2)}
        </pre>
      </details>
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading…</p>}>
      <ResultsContent />
    </Suspense>
  );
}
