import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Analysis, Config, Filters } from "../types";
import { LABELS } from "../types";
import { AnalysisCard } from "./AnalysisCard";
import { DetailModal } from "./DetailModal";

const PAGE = 24;

export function History({ config, refreshKey, onChanged }: { config: Config; refreshKey: number; onChanged: () => void }) {
  const [f, setF] = useState<Filters>({ labels: [], needs_review: false, cleaning_activated: false });
  const [items, setItems] = useState<Analysis[]>([]);
  const [total, setTotal] = useState(0);
  const [open, setOpen] = useState<Analysis | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (offset = 0) => {
    setLoading(true);
    try {
      const r = await api.list(f, PAGE, offset);
      setItems((prev) => (offset ? [...prev, ...r.itens] : r.itens));
      setTotal(r.total); setErr(null);
    } catch (e) { setErr(e instanceof Error ? e.message : "Falha ao carregar."); } finally { setLoading(false); }
  }, [f]);

  useEffect(() => { void load(0); }, [load, refreshKey]);

  const toggle = (l: (typeof LABELS)[number]) => setF((p) => ({ ...p, labels: p.labels.includes(l) ? p.labels.filter((x) => x !== l) : [...p.labels, l] }));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filtros">
        {LABELS.map((l) => <button key={l} className="chip" aria-pressed={f.labels.includes(l)} onClick={() => toggle(l)}>{l}</button>)}
        <button className="chip" aria-pressed={f.needs_review} onClick={() => setF((p) => ({ ...p, needs_review: !p.needs_review }))}>Para revisar</button>
        <button className="chip" aria-pressed={f.cleaning_activated} onClick={() => setF((p) => ({ ...p, cleaning_activated: !p.cleaning_activated }))}>💧 Bomba acionada</button>
        <span className="ml-auto text-sm text-stone-500">{total} análise(s)</span>
      </div>
      {err && <p role="alert" className="text-red-700 dark:text-red-300">{err}</p>}
      {!loading && items.length === 0 && !err && <p className="card text-stone-500">Nenhuma análise com esses filtros ainda.</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {items.map((a) => <AnalysisCard key={a.id} a={a} onOpen={setOpen} />)}
      </div>
      {items.length < total && <button className="btn btn-ghost w-full" disabled={loading} onClick={() => load(items.length)}>Carregar mais</button>}
      {open && <DetailModal a={open} config={config} onClose={() => setOpen(null)} onChanged={() => { onChanged(); void load(0); }} />}
    </div>
  );
}
