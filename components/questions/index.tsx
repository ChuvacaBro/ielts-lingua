"use client";

/**
 * One <QuestionView> dispatches to the right sub-component by question type.
 * In review mode each component additionally renders correctness highlight.
 */
import type { AnswerValue, Question } from "@/lib/types";

type QV = {
  q: Question;
  value: AnswerValue | undefined;
  onChange: (v: AnswerValue) => void;
  disabled?: boolean;
  correct?: AnswerValue;
};

export function QuestionView({ q, value, onChange, disabled, correct }: QV) {
  const review = correct !== undefined;
  switch (q.type) {
    case "multipleChoice":
      return (
        <MCQ
          q={q}
          value={(value as string) || ""}
          onChange={onChange}
          disabled={disabled}
          correct={correct as string | undefined}
        />
      );
    case "tfng":
      return (
        <Choice
          q={q}
          choices={["TRUE", "FALSE", "NOT GIVEN"]}
          value={(value as string) || ""}
          onChange={onChange}
          disabled={disabled}
          correct={correct as string | undefined}
        />
      );
    case "ynng":
      return (
        <Choice
          q={q}
          choices={["YES", "NO", "NOT GIVEN"]}
          value={(value as string) || ""}
          onChange={onChange}
          disabled={disabled}
          correct={correct as string | undefined}
        />
      );
    case "matchHeadings":
      return (
        <MatchHeadings
          q={q}
          value={(value as string) || ""}
          onChange={onChange}
          disabled={disabled}
          correct={correct as string | undefined}
        />
      );
    case "unsupported":
      return (
        <div className="border border-amber-300 bg-amber-50 p-3 my-3 text-sm">
          <div className="font-semibold mb-1">Question {q.number}</div>
          <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: q.rawHtml }}
          />
          <label className="block mt-2">
            Your answer:{" "}
            <input
              className="exam-input"
              value={(value as string) || ""}
              onChange={(e) => onChange(e.target.value)}
              disabled={disabled}
            />
          </label>
          {review && (
            <div className="mt-1 text-xs text-gray-700">
              Correct: <span className="font-mono">{String(correct)}</span>
            </div>
          )}
        </div>
      );
    default:
      return (
        <GapFill
          q={q}
          value={(value as string) || ""}
          onChange={onChange}
          disabled={disabled}
          correct={correct as string | undefined}
        />
      );
  }
}

// ---- specific components ---------------------------------------------------

function ReviewBadge({ user, correct }: { user: AnswerValue | undefined; correct: AnswerValue }) {
  if (user === undefined) return <span className="text-gray-500 ml-2">(no answer)</span>;
  const ok =
    Array.isArray(user) && Array.isArray(correct)
      ? user.length === correct.length && user.every((v) => correct.includes(v))
      : String(user).toLowerCase().trim() === String(correct).toLowerCase().trim();
  return (
    <span className={"ml-2 " + (ok ? "text-green-700" : "text-red-700")}>
      {ok ? "✓" : "✗"} correct: <span className="font-mono">{String(correct)}</span>
    </span>
  );
}

function MCQ({
  q,
  value,
  onChange,
  disabled,
  correct,
}: {
  q: Extract<Question, { type: "multipleChoice" }>;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  correct?: string;
}) {
  return (
    <div className="my-3">
      <div className="font-medium mb-1">
        {q.number}. {q.stem}
      </div>
      {q.options.map((opt) => (
        <label key={opt.letter} className="block ml-4 my-0.5">
          <input
            type="radio"
            name={`q${q.number}`}
            checked={value === opt.letter}
            onChange={() => onChange(opt.letter)}
            disabled={disabled}
            className="mr-2"
          />
          <span className="font-mono mr-1">{opt.letter}</span> {opt.text}
        </label>
      ))}
      {correct !== undefined && <ReviewBadge user={value} correct={correct} />}
    </div>
  );
}

function Choice({
  q,
  choices,
  value,
  onChange,
  disabled,
  correct,
}: {
  q: Question;
  choices: string[];
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  correct?: string;
}) {
  const statement = (q as any).statement || (q as any).prompt || "";
  return (
    <div className="my-3 flex items-start gap-3">
      <div className="font-medium min-w-[1.5rem]">{q.number}.</div>
      <div className="flex-1">
        <div className="mb-1">{statement}</div>
        <div className="flex gap-2 flex-wrap">
          {choices.map((c) => (
            <label
              key={c}
              className={
                "px-2 py-1 border cursor-pointer text-sm " +
                (value === c
                  ? "bg-exam-accent text-white border-exam-accent"
                  : "bg-white border-gray-400")
              }
            >
              <input
                type="radio"
                className="hidden"
                name={`q${q.number}`}
                checked={value === c}
                onChange={() => onChange(c)}
                disabled={disabled}
              />
              {c}
            </label>
          ))}
        </div>
        {correct !== undefined && <ReviewBadge user={value} correct={correct} />}
      </div>
    </div>
  );
}

function MatchHeadings({
  q,
  value,
  onChange,
  disabled,
  correct,
}: {
  q: Extract<Question, { type: "matchHeadings" }>;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  correct?: string;
}) {
  return (
    <div className="my-3 flex items-start gap-3">
      <div className="font-medium">{q.number}.</div>
      <div className="flex-1">
        <div className="mb-1">Paragraph {q.paragraphLetter}</div>
        <select
          className="exam-input min-w-[14rem]"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
        >
          <option value="">— choose heading —</option>
          {(q.headings || []).map((h) => (
            <option key={h.number} value={h.number}>
              {h.number}. {h.text}
            </option>
          ))}
        </select>
        {correct !== undefined && <ReviewBadge user={value} correct={correct} />}
      </div>
    </div>
  );
}

function GapFill({
  q,
  value,
  onChange,
  disabled,
  correct,
}: {
  q: Question;
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  correct?: string;
}) {
  const prompt = (q as any).prompt || (q as any).statement || "";
  const wordLimit = (q as any).wordLimit;
  return (
    <div className="my-3 flex items-start gap-3">
      <div className="font-medium min-w-[1.5rem]">{q.number}.</div>
      <div className="flex-1">
        <div className="text-sm text-gray-700">{prompt}</div>
        <input
          className="exam-input mt-1 w-72"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={wordLimit || "your answer"}
          disabled={disabled}
        />
        {correct !== undefined && <ReviewBadge user={value} correct={correct} />}
      </div>
    </div>
  );
}
