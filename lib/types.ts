/**
 * Shared TypeScript types for the IELTS CB mock platform.
 * The runtime data in content/*.json conforms to these shapes.
 * See DESIGN.md §3 for the rationale.
 */

export type QType =
  | "multipleChoice"
  | "tfng"
  | "ynng"
  | "matchHeadings"
  | "matchInfo"
  | "matchFeatures"
  | "matchEndings"
  | "sentenceCompletion"
  | "summaryCompletion"
  | "noteCompletion"
  | "tableCompletion"
  | "formCompletion"
  | "flowChartCompletion"
  | "diagramLabel"
  | "mapPlanLabelling"
  | "shortAnswer"
  | "gapFill" // generic fall-back for un-categorised single-input questions
  | "unsupported";

export interface BaseQ {
  number: number;
  type: QType;
  /** Identifies a contiguous block of questions sharing instructions. */
  groupId: string;
  instructions?: string;
}

export interface MultipleChoiceQ extends BaseQ {
  type: "multipleChoice";
  stem: string;
  options: { letter: string; text: string }[];
  multiSelect?: boolean;
}

export interface TFNGQ extends BaseQ {
  type: "tfng";
  statement: string;
}

export interface YNNGQ extends BaseQ {
  type: "ynng";
  statement: string;
}

export interface MatchHeadingsQ extends BaseQ {
  type: "matchHeadings";
  paragraphLetter: string;
  headings: { number: string; text: string }[];
}

export interface MatchInfoQ extends BaseQ {
  type: "matchInfo";
  statement: string;
  paragraphLetters: string[];
}

export interface MatchFeaturesQ extends BaseQ {
  type: "matchFeatures";
  statement: string;
  features: { letter: string; text: string }[];
}

export interface MatchEndingsQ extends BaseQ {
  type: "matchEndings";
  beginning: string;
  endings: { letter: string; text: string }[];
}

export interface GapFillQ extends BaseQ {
  type:
    | "sentenceCompletion"
    | "summaryCompletion"
    | "noteCompletion"
    | "tableCompletion"
    | "formCompletion"
    | "flowChartCompletion"
    | "diagramLabel"
    | "mapPlanLabelling"
    | "shortAnswer"
    | "gapFill";
  /** Free text surrounding the blank. UI renders <prompt> with the blank highlighted. */
  prompt: string;
  /** Optional letter bank for summary-completion-with-list variants. */
  bank?: { letter: string; text: string }[];
  imageUrl?: string;
  wordLimit?: string;
}

export interface UnsupportedQ extends BaseQ {
  type: "unsupported";
  rawHtml: string;
}

export type Question =
  | MultipleChoiceQ
  | TFNGQ
  | YNNGQ
  | MatchHeadingsQ
  | MatchInfoQ
  | MatchFeaturesQ
  | MatchEndingsQ
  | GapFillQ
  | UnsupportedQ;

export type AnswerValue = string | string[];

export interface ReadingPassage {
  number: 1 | 2 | 3;
  title: string;
  /** HTML for the passage body, ad scripts stripped. */
  bodyHtml: string;
  imageUrl?: string;
}

export interface ReadingTest {
  id: string;
  variant: "academic";
  source: "html" | "docx" | "v2";
  passages: ReadingPassage[];
  questions: Question[];
  answerKey: Record<string, AnswerValue>;
}

export interface ListeningPart {
  number: 1 | 2 | 3 | 4;
  instructions: string;
  questionRange: [number, number];
  imageUrl?: string;
}

export interface ListeningTest {
  id: string;
  parts: ListeningPart[];
  audioUrl?: string | null;
  localAudioPath?: string | null;
  questions: Question[];
  answerKey: Record<string, AnswerValue>;
}

export interface WritingTest {
  id: string;
  task1: { prompt: string; imageUrl?: string; minWords: 150 };
  task2: { prompt: string; minWords: 250 };
}

export interface SpeakingTest {
  id: string;
  topic: string;
  part1: { questions: string[] };
  part2: {
    cueCard: string;
    bulletPoints: string[];
    prepSeconds: 60;
    answerSeconds: 120;
  };
  part3: { questions: string[] };
}

export interface CatalogEntry {
  id: string;
  /** Coarse availability flags so the home page can pre-filter. */
  flags: Record<string, boolean | number | string>;
}

export interface Catalog {
  reading: CatalogEntry[];
  listening: CatalogEntry[];
  writing: CatalogEntry[];
  speaking: CatalogEntry[];
  generatedAt: string;
}
