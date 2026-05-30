"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

type Stage = "listening" | "reading" | "writing" | "speaking" | "done";

type State = {
  id: string;
  reading: string;
  listening: string;
  writing: string;
  speaking: string;
  currentStage: Stage;
};

const ORDER: Stage[] = ["listening", "reading", "writing", "speaking", "done"];

function FullMockContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const [state, setState] = useState<State | null>(null);

  useEffect(() => {
    const raw = window.localStorage.getItem(`ielts.fullMock.${id}`);
    if (raw) setState(JSON.parse(raw));
  }, [id]);

  function advance() {
    if (!state) return;
    const idx = ORDER.indexOf(state.currentStage);
    const next = ORDER[Math.min(idx + 1, ORDER.length - 1)];
    const updated = { ...state, currentStage: next };
    window.localStorage.setItem(`ielts.fullMock.${id}`, JSON.stringify(updated));
    setState(updated);
  }

  if (!state) return <p className="p-6">Loading…</p>;

  const titles: Record<Stage, string> = {
    listening: "Listening",
    reading: "Reading",
    writing: "Writing",
    speaking: "Speaking",
    done: "Done",
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <Link href="/" className="text-exam-accent text-sm">
        ← Home
      </Link>
      <h1 className="text-2xl font-semibold mt-2 mb-4">Full Mock {id.slice(0, 8)}</h1>
      <ol className="space-y-3">
        {(["listening", "reading", "writing", "speaking"] as Stage[]).map((s) => {
          const idx = ORDER.indexOf(s);
          const currentIdx = ORDER.indexOf(state.currentStage);
          const done = idx < currentIdx;
          const active = idx === currentIdx;
          const testId =
            s === "listening" ? state.listening :
            s === "reading"   ? state.reading   :
            s === "writing"   ? state.writing   :
            state.speaking;
          return (
            <li
              key={s}
              className={
                "border border-exam-border p-3 flex items-center gap-3 " +
                (active ? "bg-blue-50 border-exam-accent" : "")
              }
            >
              <span className="font-mono text-sm w-6">{done ? "✓" : idx + 1}</span>
              <span className="flex-1">
                {titles[s]} — test <span className="font-mono">{testId}</span>
              </span>
              {active && (
                <>
                  <Link href={`/${s}/${testId}`} className="bg-exam-accent text-white px-3 py-1 text-sm">
                    Start
                  </Link>
                  <button onClick={advance} className="border px-3 py-1 text-sm">
                    Mark done →
                  </button>
                </>
              )}
              {done && <span className="text-green-700 text-sm">done</span>}
            </li>
          );
        })}
      </ol>
      {state.currentStage === "done" && (
        <p className="mt-4 text-green-700">
          Mock complete — Reading and Listening results are in{" "}
          <Link href="/history" className="text-exam-accent underline">
            attempt history
          </Link>
          . Writing and Speaking are saved under My Essays / My Speaking.
        </p>
      )}
    </div>
  );
}

export default function FullMockPage() {
  return (
    <Suspense fallback={<p className="p-6">Loading…</p>}>
      <FullMockContent />
    </Suspense>
  );
}
