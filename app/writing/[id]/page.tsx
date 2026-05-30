import WritingRunner from "@/components/writing/WritingRunner";
import { loadCatalog, loadWriting } from "@/lib/content/loader";

export function generateStaticParams() {
  const cat = loadCatalog();
  return cat.writing.map((r) => ({ id: r.id }));
}

export default function WritingPage({ params }: { params: { id: string } }) {
  const test = loadWriting(params.id);
  return <WritingRunner test={test} />;
}
