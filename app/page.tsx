import Link from "next/link";
import { loadCatalog } from "@/lib/content/loader";
import { HomeActions } from "./HomeActions";

export default function HomePage() {
  const cat = loadCatalog();
  return (
    <main className="max-w-6xl mx-auto p-6">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold">IELTS CB Mock Tests</h1>
        <p className="text-gray-600 mt-1">
          Computer-Delivered IELTS practice. Reading & Listening are auto-graded
          with band-score conversion. Writing & Speaking are saved for later
          review (no auto-grading).
        </p>
      </header>

      <HomeActions
        readingIds={cat.reading.map((r) => r.id)}
        listeningIds={cat.listening.map((r) => r.id)}
        writingIds={cat.writing.map((r) => r.id)}
        speakingIds={cat.speaking.map((r) => r.id)}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
        <Section
          title="Reading"
          subtitle={`${cat.reading.length} tests — 60 min, 40 questions, Academic`}
          base="/reading"
          ids={cat.reading.map((r) => r.id)}
        />
        <Section
          title="Listening"
          subtitle={`${cat.listening.length} tests — ~30 min, 40 questions, 4 parts`}
          base="/listening"
          ids={cat.listening.map((r) => r.id)}
        />
        <Section
          title="Writing"
          subtitle={`${cat.writing.length} tests — 60 min, Task 1 + Task 2`}
          base="/writing"
          ids={cat.writing.map((r) => r.id)}
        />
        <Section
          title="Speaking"
          subtitle={`${cat.speaking.length} topics — 3 parts incl. cue card`}
          base="/speaking"
          ids={cat.speaking.map((r) => r.id)}
        />
      </div>

      <footer className="mt-10 text-sm text-gray-600 flex gap-4">
        <Link href="/my-essays" className="text-exam-accent">My Writing Essays</Link>
        <Link href="/my-speaking" className="text-exam-accent">My Speaking Answers</Link>
        <Link href="/history" className="text-exam-accent">Attempt History</Link>
      </footer>
    </main>
  );
}

function Section({
  title,
  subtitle,
  base,
  ids,
}: {
  title: string;
  subtitle: string;
  base: string;
  ids: string[];
}) {
  return (
    <div className="border border-exam-border p-4">
      <div className="flex items-baseline justify-between mb-2">
        <h2 className="text-xl font-semibold">{title}</h2>
        <span className="text-xs text-gray-500">{subtitle}</span>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-exam-accent">
          Browse {ids.length} tests
        </summary>
        <div className="grid grid-cols-6 sm:grid-cols-10 gap-1 mt-2 max-h-64 overflow-y-auto">
          {ids.map((id) => (
            <Link
              key={id}
              href={`${base}/${id}`}
              className="text-center border border-gray-300 py-1 hover:bg-gray-100 text-xs"
            >
              {parseInt(id, 10)}
            </Link>
          ))}
        </div>
      </details>
    </div>
  );
}
