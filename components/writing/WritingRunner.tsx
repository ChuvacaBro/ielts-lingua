"use client";

import { useEffect, useRef, useState } from "react";
import type { WritingTest } from "@/lib/types";
import { ImageWithLoader } from "@/components/ui/ImageWithLoader";
import { useExamTimer } from "@/components/timer/useExamTimer";
import { TopTimer } from "@/components/timer/TopTimer";
import { Essays } from "@/lib/storage/local";
import { useRouter } from "next/navigation";

const DURATION = 60 * 60;

function wordCount(s: string): number {
  return s.trim().split(/\s+/).filter(Boolean).length;
}

export default function WritingRunner({ test }: { test: WritingTest }) {
  const router = useRouter();
  const startedAt = useRef(new Date().toISOString());
  const [tab, setTab] = useState<"task1" | "task2">("task1");
  const [task1, setTask1] = useState("");
  const [task2, setTask2] = useState("");
  const [warn, setWarn] = useState<string | null>(null);

  const { remaining } = useExamTimer({
    durationSec: DURATION,
    onWarn10: () => setWarn("10 minutes remaining"),
    onWarn5: () => setWarn("5 minutes remaining"),
    onExpire: () => doSubmit(),
  });

  // Autosave every 5 seconds.
  useEffect(() => {
    const t = setInterval(() => {
      Essays.save({
        testId: test.id,
        timestamp: startedAt.current,
        task1,
        task2,
      });
    }, 5000);
    return () => clearInterval(t);
  }, [test.id, task1, task2]);

  function doSubmit() {
    Essays.save({
      testId: test.id,
      timestamp: startedAt.current,
      task1,
      task2,
    });
    router.push("/my-essays");
  }

  const wc = tab === "task1" ? wordCount(task1) : wordCount(task2);
  const minWords = tab === "task1" ? test.task1.minWords : test.task2.minWords;
  const prompt = tab === "task1" ? test.task1.prompt : test.task2.prompt;
  const imageUrl = tab === "task1" ? test.task1.imageUrl : undefined;
  const value = tab === "task1" ? task1 : task2;
  const setValue = tab === "task1" ? setTask1 : setTask2;

  return (
    <div className="flex flex-col min-h-screen">
      <TopTimer
        remaining={remaining}
        label={`Writing — Test ${test.id}`}
        warn={remaining <= 300}
      />
      {warn && (
        <div className="bg-amber-100 border-b border-amber-300 px-4 py-1 text-sm">
          {warn}
          <button className="float-right text-xs" onClick={() => setWarn(null)}>
            dismiss
          </button>
        </div>
      )}
      <div className="border-b border-exam-border flex">
        <button
          className={
            "px-4 py-2 text-sm border-r border-exam-border " +
            (tab === "task1" ? "bg-exam-accent text-white" : "bg-white")
          }
          onClick={() => setTab("task1")}
        >
          Task 1 ({wordCount(task1)} words)
        </button>
        <button
          className={
            "px-4 py-2 text-sm " +
            (tab === "task2" ? "bg-exam-accent text-white" : "bg-white")
          }
          onClick={() => setTab("task2")}
        >
          Task 2 ({wordCount(task2)} words)
        </button>
        <button
          className="ml-auto px-4 py-2 text-sm bg-exam-accent text-white"
          onClick={doSubmit}
        >
          Save & Finish
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 flex-1 overflow-hidden">
        <div className="border-r border-exam-border p-5 overflow-y-auto">
          <div className="font-semibold mb-2">
            {tab === "task1" ? "Task 1" : "Task 2"}
          </div>
          <p className="mb-3 leading-relaxed">{prompt}</p>
          <p className="text-sm text-gray-600">
            Write at least {minWords} words.
          </p>
          {imageUrl && (
            <ImageWithLoader
              src={imageUrl}
              alt="Task 1 figure"
              className="my-3 border border-exam-border max-w-full"
            />
          )}
        </div>
        <div className="p-5 flex flex-col">
          <textarea
            className="flex-1 border border-exam-border p-3 font-exam text-base resize-none min-h-[400px]"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={`Write your ${tab === "task1" ? "Task 1" : "Task 2"} response here…`}
          />
          <div className="text-sm mt-2 flex justify-between">
            <span className={wc < minWords ? "text-red-700" : "text-green-700"}>
              {wc} / {minWords} words
            </span>
            <span className="text-gray-600">Autosaves every 5 seconds.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
