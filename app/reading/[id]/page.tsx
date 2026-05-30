import ReadingRunner from "@/components/reading/ReadingRunner";
import { loadReading, loadCatalog } from "@/lib/content/loader";

export function generateStaticParams() {
  const cat = loadCatalog();
  return cat.reading.map((r) => ({ id: r.id }));
}

export default function ReadingPage({ params }: { params: { id: string } }) {
  const test = loadReading(params.id);
  return <ReadingRunner test={test} />;
}
