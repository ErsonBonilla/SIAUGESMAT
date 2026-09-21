import type { JSX } from "preact";
import Disposicion from "./Disposicion.tsx";
import TarjetaHub from "./TarjetaHub.tsx";

export interface DefinicionTarjetaHub {
  icon: (props: { class?: string }) => JSX.Element;
  title: string;
  description: string;
  href: string;
}

interface Props {
  title: string;
  cards: DefinicionTarjetaHub[];
}

export default function PaginaHub({ title, cards }: Props) {
  const cols = cards.length === 2
    ? "sm:grid-cols-2"
    : cards.length === 4
    ? "sm:grid-cols-2 lg:grid-cols-4"
    : "sm:grid-cols-3";

  return (
    <Disposicion title={title}>
      <div class={`grid grid-cols-1 ${cols} gap-6`}>
        {cards.map((c) => <TarjetaHub key={c.href} {...c} />)}
      </div>
    </Disposicion>
  );
}
