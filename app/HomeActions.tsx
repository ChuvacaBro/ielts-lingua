"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

function pick(arr: string[]) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function HomeActions({
  readingIds,
  listeningIds,
  writingIds,
  speakingIds,
}: {
  readingIds: string[];
  listeningIds: string[];
  writingIds: string[];
  speakingIds: string[];
}) {
  const router = useRouter();

  function fullMock() {
    const id = crypto.randomUUID();
    const state = {
      id,
      reading: pick(readingIds),
      listening: pick(listeningIds),
      writing: pick(writingIds),
      speaking: pick(speakingIds),
      currentStage: "listening" as const,
    };
    window.localStorage.setItem(`ielts.fullMock.${id}`, JSON.stringify(state));
    router.push(`/full-mock?id=${id}`);
  }

  return (
    <div className="border border-exam-border p-4 mb-2 grid grid-cols-1 sm:grid-cols-5 gap-2 text-sm">
      <button
        className="bg-exam-accent text-white py-2 col-span-1 sm:col-span-2"
        onClick={fullMock}
      >
        🚀 Full Mock (L → R → W → S, random tests)
      </button>
      <Link href={`/reading/${pick(readingIds)}`} className="border py-2 text-center">
        🎲 Random Reading
      </Link>
      <Link href={`/listening/${pick(listeningIds)}`} className="border py-2 text-center">
        🎲 Random Listening
      </Link>
      <Link href={`/writing/${pick(writingIds)}`} className="border py-2 text-center">
        🎲 Random Writing
      </Link>
      <Link href={`/speaking/${pick(speakingIds)}`} className="border py-2 text-center">
        🎲 Random Speaking
      </Link>
    </div>
  );
}
