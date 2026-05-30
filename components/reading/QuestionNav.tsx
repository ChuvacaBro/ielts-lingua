"use client";

export function QuestionNav({
  questionNumbers,
  current,
  answered,
  flagged,
  onJump,
  onSubmit,
}: {
  questionNumbers: number[];
  current: number;
  answered: Set<number>;
  flagged: Set<number>;
  onJump: (n: number) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="sticky bottom-0 left-0 right-0 z-40 border-t border-exam-border bg-white px-3 py-2">
      <div className="exam-question-nav flex flex-wrap gap-1">
        {questionNumbers.map((n) => (
          <button
            key={n}
            onClick={() => onJump(n)}
            className={
              "relative " +
              (answered.has(n) ? "answered " : "") +
              (n === current ? "current " : "") +
              (flagged.has(n) ? "flagged " : "")
            }
          >
            {n}
          </button>
        ))}
        <button
          onClick={onSubmit}
          className="ml-auto bg-exam-accent text-white px-4 py-1 text-sm"
        >
          Submit
        </button>
      </div>
    </div>
  );
}
