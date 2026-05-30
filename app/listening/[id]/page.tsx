import ListeningRunner from "@/components/listening/ListeningRunner";
import { loadCatalog, loadListening } from "@/lib/content/loader";

export function generateStaticParams() {
  const cat = loadCatalog();
  return cat.listening.map((r) => ({ id: r.id }));
}

export default function ListeningPage({ params }: { params: { id: string } }) {
  const test = loadListening(params.id);
  return <ListeningRunner test={test} />;
}
