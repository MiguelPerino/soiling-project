import type { Label } from "../types";

/** Cores e textos das duas classes (verde / vermelho). O código (LIMPO/SEVERO) só aparece na API e no banco. */
export const LABEL_STYLE: Record<Label, { solid: string; text: string; desc: string }> = {
  LIMPO: { solid: "#27aa77", text: "Não precisa limpar", desc: "O painel não precisa de limpeza" },
  SEVERO: { solid: "#e75c5e", text: "Precisa limpar", desc: "O painel precisa de limpeza" },
};

/** Texto da classe na tela. Valor desconhecido (ex.: análise antiga de 3 classes) aparece como veio. */
export const labelText = (l: string) => LABEL_STYLE[l as Label]?.text ?? l;

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(0)}%`);
/** Uma casa decimal, com vírgula: 0.942 -> "94,2%". */
export const pct1 = (v: number | null | undefined) => (v == null ? "—" : `${(v * 100).toFixed(1).replace(".", ",")}%`);

export function when(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** "Hoje", "Ontem" ou "12 nov". */
export function dayLabel(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const yesterday = new Date();
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === now.toDateString()) return "Hoje";
  if (d.toDateString() === yesterday.toDateString()) return "Ontem";
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "");
}

export const hourLabel = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

export function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : 1)} s`;
}

/** 1815 -> "1,8 s"; abaixo de 1 s mostra em ms. */
export function duration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2).replace(".", ",")} s` : `${ms} ms`;
}
