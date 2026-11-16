import type { Label } from "../types";

/** Cores e textos das classes. As cores seguem o design SolarEye (verde / âmbar / vermelho). */
export const LABEL_STYLE: Record<Label, { solid: string; desc: string }> = {
  LIMPO: { solid: "#27aa77", desc: "Painel limpo" },
  MODERADO: { solid: "#edb23b", desc: "Poeira moderada" },
  SEVERO: { solid: "#e75c5e", desc: "Sujeira severa" },
};

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
