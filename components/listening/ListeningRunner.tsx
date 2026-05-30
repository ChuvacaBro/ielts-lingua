"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ListeningTest, AnswerValue } from "@/lib/types";
import { ImageWithLoader } from "@/components/ui/ImageWithLoader";
import { useExamTimer } from "@/components/timer/useExamTimer";
import { TopTimer } from "@/components/timer/TopTimer";
import { QuestionView } from "@/components/questions";
import { QuestionNav } from "@/components/reading/QuestionNav";
import { OnceAudio } from "./OnceAudio";
import { Attempts } from "@/lib/storage/local";
import { LISTENING_BANDS, gradeAnswers, rawToBand } from "@/lib/grading/band";
import { useRouter } from "next/navigation";

const REVIEW_TAIL_SEC = 2 * 60; // 2 minutes of review after audio ends

export default function ListeningRunner({ test }: { test: ListeningTest }) {
  const router = useRouter();
  const attemptIdRef = useRef<string>(crypto.randomUUID());
  const attemptId = attemptIdRef.current;

  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({});
  const [flags, setFlags] = useState<Set<number>>(new Set());
  const [current, setCurrent] = useState<number>(test.questions[0]?.number ?? 1);
  const [submitted, setSubmitted] = useState(false);
  const [audioEnded, setAudioEnded] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [durationSec, setDurationSec] = useState<number | null>(null);

  const questionNumbers = useMemo(
    () => test.questions.map((q) => q.number).sort((a, b) => a - b),
    [test],
  );

  // Total timer = audio duration + 2 min review. While audio plays we don't
  // surface countdown (user can't pause anyway); after it ends, we show the
  // 2-minute review window.
  const reviewTimer = useExamTimer({
    durationSec: REVIEW_TAIL_SEC,
    startImmediately: false,
    onWarn10: () => {},
    onWarn5: () => {},
    onExpire: () => doSubmit(),
  });

  useEffect(() => {
    Attempts.saveAnswers(attemptId, answers as Record<string, string | string[]>);
  }, [answers, attemptId]);

  useEffect(() => {
    Attempts.upsert({
      id: attemptId,
      section: "listening",
      testId: test.id,
      startedAt: new Date().toISOString(),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // pick best audio source: local file if exists else remote URL
  const audioSrc =
    (test.localAudioPath && test.localAudioPath) ||
    test.audioUrl ||
    "";

  function doSubmit() {
    if (submitted) return;
    const { raw, total } = gradeAnswers(
      test.answerKey,
      answers as Record<string, AnswerValue>,
    );
    const band = rawToBand(raw, LISTENING_BANDS);
    Attempts.upsert({
      id: attemptId,
      section: "listening",
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

  // total-elapsed timer (rough): we just show audio status while it plays,
  // then switch to a 2-minute review countdown.
  return (
    <div className="flex flex-col min-h-screen">
      <TopTimer
        remaining={audioEnded ? reviewTimer.remaining : currentTime}
        prefix={audioEnded ? undefined : "elapsed"}
        label={
          audioEnded
            ? "Listening — Review (2 min)"
            : `Listening — Test ${test.id} (audio playing)`
        }
        warn={audioEnded && reviewTimer.remaining <= 30}
      />
      <div className="px-5 py-3">
        {audioSrc ? (
          <OnceAudio
            src={audioSrc}
            onLoadedMetadata={(d) => setDurationSec(Math.ceil(d))}
            onTimeUpdate={(t) => setCurrentTime(Math.floor(t))}
            onEnded={() => {
              setAudioEnded(true);
              reviewTimer.start();
            }}
          />
        ) : (
          <div className="border border-red-300 bg-red-50 p-3 text-sm">
            No audio attached to this test. Either run{" "}
            <code className="font-mono">npm run fetch:audio</code> or place an
            MP3 at <code className="font-mono">public/audio/{test.id}.mp3</code>.
          </div>
        )}
      </div>
      <div className="px-5 pb-28 overflow-y-auto">
        {test.parts.map((p) => (
          <div key={p.number} className="mb-6">
            <h3 className="font-semibold mb-2">
              Part {p.number} — Questions {p.questionRange[0]}–{p.questionRange[1]}
            </h3>
            {p.imageUrl && (
              <ImageWithLoader
                src={p.imageUrl}
                alt={`Part ${p.number}`}
                className="my-2 border border-exam-border max-w-xl"
              />
            )}
            {test.questions
              .filter(
                (q) =>
                  q.number >= p.questionRange[0] && q.number <= p.questionRange[1],
              )
              .map((q) => (
                <div
                  key={q.number}
                  id={`q-${q.number}`}
                  onFocus={() => setCurrent(q.number)}
                >
                  <QuestionView
                    q={q}
                    value={answers[q.number]}
                    onChange={(v) => setAnswers((a) => ({ ...a, [q.number]: v }))}
                  />
                </div>
              ))}
          </div>
        ))}
      </div>
      <QuestionNav
        questionNumbers={questionNumbers}
        current={current}
        answered={new Set(Object.keys(answers).map((n) => parseInt(n, 10)))}
        flagged={flags}
        onJump={(n) => {
          setCurrent(n);
          document.getElementById(`q-${n}`)?.scrollIntoView({ block: "start" });
        }}
        onSubmit={doSubmit}
      />
    </div>
  );
}
