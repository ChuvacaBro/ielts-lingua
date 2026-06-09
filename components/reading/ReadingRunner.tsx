"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ReadingTest, AnswerValue } from "@/lib/types";
import { useExamTimer } from "@/components/timer/useExamTimer";
import { TopTimer } from "@/components/timer/TopTimer";
import { QuestionView } from "@/components/questions";
import { ImageWithLoader } from "@/components/ui/ImageWithLoader";
import { QuestionNav } from "./QuestionNav";
import { Attempts } from "@/lib/storage/local";
import {
  ACADEMIC_READING_BANDS,
  gradeAnswers,
  rawToBand,
} from "@/lib/grading/band";
import { useRouter } from "next/navigation";

const DURATION = 60 * 60; // 60 minutes

export default function ReadingRunner({ test }: { test: ReadingTest }) {
  const router = useRouter();
  const attemptIdRef = useRef<string>(crypto.randomUUID());
  const attemptId = attemptIdRef.current;

  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({});
  const [flags, setFlags] = useState<Set<number>>(new Set());
  const [current, setCurrent] = useState<number>(
    test.questions[0]?.number ?? 1,
  );
  const [activePart, setActivePart] = useState<number>(
    test.passages[0]?.number ?? 1,
  );
  const [submitted, setSubmitted] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);

  const partOf = (n: number) =>
    test.passages.find(
      (p) => n >= p.questionRange[0] && n <= p.questionRange[1],
    )?.number;

  const activePassage =
    test.passages.find((p) => p.number === activePart) ?? test.passages[0];

  function goToQuestion(n: number) {
    setCurrent(n);
    const part = partOf(n);
    if (part) setActivePart(part);
    requestAnimationFrame(() =>
      document.getElementById(`q-${n}`)?.scrollIntoView({ block: "start" }),
    );
  }

  const questionNumbers = useMemo(
    () => test.questions.map((q) => q.number).sort((a, b) => a - b),
    [test],
  );

  const { remaining } = useExamTimer({
    durationSec: DURATION,
    onWarn10: () => setWarn("10 minutes remaining"),
    onWarn5: () => setWarn("5 minutes remaining"),
    onExpire: () => doSubmit(),
  });

  // persist on every change
  useEffect(() => {
    Attempts.saveAnswers(
      attemptId,
      answers as Record<string, string | string[]>,
    );
  }, [answers, attemptId]);

  useEffect(() => {
    Attempts.saveFlags(attemptId, Array.from(flags));
  }, [flags, attemptId]);

  useEffect(() => {
    Attempts.upsert({
      id: attemptId,
      section: "reading",
      testId: test.id,
      startedAt: new Date().toISOString(),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function doSubmit() {
    if (submitted) return;
    const { raw, total } = gradeAnswers(
      test.answerKey,
      answers as Record<string, AnswerValue>,
    );
    const band = rawToBand(raw, ACADEMIC_READING_BANDS);
    Attempts.upsert({
      id: attemptId,
      section: "reading",
      testId: test.id,
      startedAt: new Date().toISOString(),
      finishedAt: new Date().toISOString(),
      raw,
      total,
      band,
    });
    setSubmitted(true);
    router.push(`/results?id=${attemptId}`);
  }

  const currentQ = test.questions.find((q) => q.number === current);

  return (
    <div className="flex flex-col min-h-screen">
      <TopTimer
        remaining={remaining}
        label={`Reading — Test ${test.id}`}
        warn={remaining <= 300}
      />
      {warn && (
        <div className="bg-amber-100 border-b border-amber-300 px-4 py-1 text-sm text-amber-900">
          {warn}
          <button className="float-right text-xs" onClick={() => setWarn(null)}>
            dismiss
          </button>
        </div>
      )}
      <div className="flex border-b border-exam-border bg-gray-50">
        {test.passages.map((p) => {
          const answeredInPart = test.questions.filter(
            (q) =>
              q.number >= p.questionRange[0] &&
              q.number <= p.questionRange[1] &&
              answers[q.number] !== undefined &&
              answers[q.number] !== "",
          ).length;
          const total = p.questionRange[1] - p.questionRange[0] + 1;
          return (
            <button
              key={p.number}
              type="button"
              onClick={() => goToQuestion(p.questionRange[0])}
              className={
                "px-4 py-2 text-sm border-r border-exam-border " +
                (p.number === activePart
                  ? "bg-white font-semibold border-b-2 border-b-exam-accent -mb-px"
                  : "text-gray-600 hover:bg-white")
              }
            >
              Part {p.number} · Q{p.questionRange[0]}–{p.questionRange[1]}
              <span className="ml-2 text-xs text-gray-500">
                {answeredInPart}/{total}
              </span>
            </button>
          );
        })}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 flex-1 overflow-hidden">
        <div className="border-r border-exam-border p-5 overflow-y-auto">
          {activePassage && (
            <div className="mb-8">
              <h2 className="font-semibold text-lg mb-3">
                Passage {activePassage.number} — Questions{" "}
                {activePassage.questionRange[0]}–
                {activePassage.questionRange[1]}
              </h2>
              <div
                className="prose prose-sm max-w-none leading-relaxed"
                dangerouslySetInnerHTML={{ __html: activePassage.bodyHtml }}
              />
              {activePassage.images?.map((src, i) => (
                <ImageWithLoader
                  key={src}
                  src={src}
                  alt={`Passage ${activePassage.number} figure ${i + 1}`}
                  className="my-3 border border-exam-border max-w-full"
                />
              ))}
            </div>
          )}
        </div>
        <div className="p-5 overflow-y-auto pb-24">
          {test.questions
            .filter(
              (q) =>
                activePassage !== undefined &&
                q.number >= activePassage.questionRange[0] &&
                q.number <= activePassage.questionRange[1],
            )
            .map((q, idx, arr) => {
              const groupStart =
                idx === 0 || arr[idx - 1].groupId !== q.groupId;
              const instructions = (q as { instructions?: string })
                .instructions;
              const bank = (q as { bank?: { letter: string; text: string }[] })
                .bank;
              return (
                <div key={q.number}>
                  {groupStart && (instructions || bank) && (
                    <div className="mb-2 mt-5 border-l-2 border-exam-accent bg-gray-50 px-3 py-2">
                      {instructions && (
                        <p className="text-sm font-medium text-gray-800">
                          {instructions}
                        </p>
                      )}
                      {bank && (
                        <ul className="mt-1 text-sm text-gray-700 space-y-0.5">
                          {bank.map((o) => (
                            <li key={o.letter}>
                              <span className="font-mono font-semibold mr-1">
                                {o.letter}
                              </span>
                              {o.text}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  <div
                    id={`q-${q.number}`}
                    onFocus={() => setCurrent(q.number)}
                    className={
                      q.number === current
                        ? "border-l-4 border-exam-accent pl-2 -ml-2"
                        : ""
                    }
                  >
                    <div className="flex justify-end -mb-2">
                      <button
                        type="button"
                        className={
                          "text-xs px-2 py-0.5 border " +
                          (flags.has(q.number)
                            ? "bg-red-100 border-red-400"
                            : "border-gray-300")
                        }
                        onClick={() =>
                          setFlags((f) => {
                            const n = new Set(f);
                            if (n.has(q.number)) n.delete(q.number);
                            else n.add(q.number);
                            return n;
                          })
                        }
                      >
                        {flags.has(q.number) ? "★ review" : "☆ review"}
                      </button>
                    </div>
                    <QuestionView
                      q={q}
                      value={answers[q.number]}
                      onChange={(v) =>
                        setAnswers((a) => ({ ...a, [q.number]: v }))
                      }
                    />
                  </div>
                </div>
              );
            })}
        </div>
      </div>
      <QuestionNav
        questionNumbers={questionNumbers}
        current={current}
        answered={new Set(Object.keys(answers).map((n) => parseInt(n, 10)))}
        flagged={flags}
        onJump={goToQuestion}
        onSubmit={doSubmit}
      />
    </div>
  );
}
