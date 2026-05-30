"use client";

import { useEffect, useRef, useState } from "react";
import type { SpeakingTest } from "@/lib/types";
import { useExamTimer, formatMMSS } from "@/components/timer/useExamTimer";
import { Speaking } from "@/lib/storage/local";
import { useRouter } from "next/navigation";

type Stage = "part1" | "part2-prep" | "part2-answer" | "part3" | "done";

export default function SpeakingRunner({ test }: { test: SpeakingTest }) {
  const router = useRouter();
  const startedAt = useRef(new Date().toISOString());
  const [stage, setStage] = useState<Stage>("part1");

  const [part1Answers, setPart1Answers] = useState<string[]>(
    Array(test.part1.questions.length).fill(""),
  );
  const [part2Answer, setPart2Answer] = useState("");
  const [part3Answers, setPart3Answers] = useState<string[]>(
    Array(test.part3.questions.length).fill(""),
  );

  // Autosave every 5 seconds.
  useEffect(() => {
    const t = setInterval(() => {
      Speaking.save({
        testId: test.id,
        timestamp: startedAt.current,
        part1: part1Answers,
        part2: part2Answer,
        part3: part3Answers,
      });
    }, 5000);
    return () => clearInterval(t);
  }, [test.id, part1Answers, part2Answer, part3Answers]);

  function finish() {
    Speaking.save({
      testId: test.id,
      timestamp: startedAt.current,
      part1: part1Answers,
      part2: part2Answer,
      part3: part3Answers,
    });
    router.push("/my-speaking");
  }

  return (
    <div className="max-w-3xl mx-auto p-6 min-h-screen">
      <h1 className="text-2xl font-semibold mb-1">Speaking — Test {test.id}</h1>
      <p className="text-gray-600 mb-6">Topic: {test.topic}</p>

      {stage === "part1" && (
        <Section title="Part 1 — Interview" onNext={() => setStage("part2-prep")}>
          {test.part1.questions.map((q, i) => (
            <div key={i} className="mb-4">
              <div className="font-medium mb-1">{q}</div>
              <textarea
                className="border border-exam-border w-full p-2 font-exam text-sm min-h-[80px]"
                value={part1Answers[i]}
                onChange={(e) => {
                  const cp = [...part1Answers];
                  cp[i] = e.target.value;
                  setPart1Answers(cp);
                }}
              />
            </div>
          ))}
        </Section>
      )}

      {stage === "part2-prep" && (
        <Part2Prep test={test} onDone={() => setStage("part2-answer")} />
      )}

      {stage === "part2-answer" && (
        <Part2Answer
          test={test}
          value={part2Answer}
          onChange={setPart2Answer}
          onDone={() => setStage("part3")}
        />
      )}

      {stage === "part3" && (
        <Section title="Part 3 — Discussion" onNext={finish} nextLabel="Save & Finish">
          {test.part3.questions.map((q, i) => (
            <div key={i} className="mb-4">
              <div className="font-medium mb-1">{q}</div>
              <textarea
                className="border border-exam-border w-full p-2 font-exam text-sm min-h-[100px]"
                value={part3Answers[i]}
                onChange={(e) => {
                  const cp = [...part3Answers];
                  cp[i] = e.target.value;
                  setPart3Answers(cp);
                }}
              />
            </div>
          ))}
        </Section>
      )}
    </div>
  );
}

function Section({
  title,
  children,
  onNext,
  nextLabel = "Next →",
}: {
  title: string;
  children: React.ReactNode;
  onNext: () => void;
  nextLabel?: string;
}) {
  return (
    <div>
      <h2 className="text-lg font-semibold mb-3">{title}</h2>
      {children}
      <button
        className="mt-2 bg-exam-accent text-white px-4 py-2"
        onClick={onNext}
      >
        {nextLabel}
      </button>
    </div>
  );
}

function Part2Prep({ test, onDone }: { test: SpeakingTest; onDone: () => void }) {
  const { remaining } = useExamTimer({
    durationSec: test.part2.prepSeconds,
    onExpire: onDone,
  });
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">Part 2 — Cue Card (preparation)</h2>
      <div className="border-2 border-exam-border p-4 mb-4">
        <div className="mb-2">{test.part2.cueCard}</div>
        <div className="text-sm text-gray-700">You should say:</div>
        <ul className="list-disc list-inside text-sm">
          {test.part2.bulletPoints.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </div>
      <div className="font-mono text-xl mb-4">Prep time left: {formatMMSS(remaining)}</div>
      <button className="bg-exam-accent text-white px-4 py-2" onClick={onDone}>
        I'm ready → start answer (2 min)
      </button>
    </div>
  );
}

function Part2Answer({
  test,
  value,
  onChange,
  onDone,
}: {
  test: SpeakingTest;
  value: string;
  onChange: (v: string) => void;
  onDone: () => void;
}) {
  const { remaining } = useExamTimer({
    durationSec: test.part2.answerSeconds,
    onExpire: onDone,
  });
  return (
    <div>
      <h2 className="text-lg font-semibold mb-2">Part 2 — Speak (answer)</h2>
      <div className="border border-exam-border p-3 text-sm mb-3 bg-gray-50">
        {test.part2.cueCard}
      </div>
      <textarea
        className="border border-exam-border w-full p-2 font-exam text-sm min-h-[200px]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Type your monologue (in the real exam you would speak it)…"
      />
      <div className="font-mono text-xl my-2">Time left: {formatMMSS(remaining)}</div>
      <button className="bg-exam-accent text-white px-4 py-2" onClick={onDone}>
        Stop & continue →
      </button>
    </div>
  );
}
