import type { Label } from "../types";

/** Sempre texto + ponto colorido, nunca só cor (acessibilidade e projetor ruim). */
export function LabelBadge({ label }: { label: Label }) {
  return (
    <span className={`label-badge ${label.toLowerCase()}`}>
      <span aria-hidden />
      {label}
    </span>
  );
}
