import type { JSX } from "preact";
import Layout from "./Layout.tsx";
import HubCard from "./HubCard.tsx";

export interface HubCardDef {
  icon: (props: { class?: string }) => JSX.Element;
  title: string;
  description: string;
  href: string;
}

interface Props {
  title: string;
  cards: HubCardDef[];
}

export default function HubPage({ title, cards }: Props) {
  const cols = cards.length === 2
    ? "sm:grid-cols-2"
    : cards.length === 4
    ? "sm:grid-cols-2 lg:grid-cols-4"
    : "sm:grid-cols-3";

  return (
    <Layout title={title}>
      <div class={`grid grid-cols-1 ${cols} gap-6`}>
        {cards.map((c) => <HubCard key={c.href} {...c} />)}
      </div>
    </Layout>
  );
}
