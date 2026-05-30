import SpeakingRunner from "@/components/speaking/SpeakingRunner";
import { loadCatalog, loadSpeaking } from "@/lib/content/loader";

export function generateStaticParams() {
  const cat = loadCatalog();
  return cat.speaking.map((r) => ({ id: r.id }));
}

export default function SpeakingPage({ params }: { params: { id: string } }) {
  const test = loadSpeaking(params.id);
  return <SpeakingRunner test={test} />;
}
