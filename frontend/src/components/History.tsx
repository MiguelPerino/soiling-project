import { Check, ChevronRight, CircleAlert, Download, Droplets, Filter, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, getAdminKey } from "../api";
import { dayLabel, hourLabel, pct } from "../lib/format";
import type { Analysis, Config, Filters } from "../types";
import { ENGINE_NAME, LABELS } from "../types";
import { DetailModal } from "./DetailModal";
import { EmptyState } from "./EmptyState";
import { EngineName } from "./EngineName";
import { LabelBadge } from "./LabelBadge";

const PAGE = 24;

export function History({ config, refreshKey, review, onChanged }: { config: Config; refreshKey: number; review: number; onChanged: () => void }) {
  const [f, setF] = useState<Filters>({ engine: "", labels: [], needs_review: false, cleaning_activated: false });
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

  const [exportMsg, setExportMsg] = useState<string | null>(null);

  const exportZip = async () => {
    setExportMsg(null);
    try {
      const blob = await api.exportTraining(true);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "fotos-para-retreino.zip";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setExportMsg(e instanceof ApiError ? e.message : "Falha ao exportar.");
    }
  };

  const toggle = (l: (typeof LABELS)[number]) => setF((p) => ({ ...p, labels: p.labels.includes(l) ? p.labels.filter((x) => x !== l) : [...p.labels, l] }));
  const filtered = f.labels.length > 0 || f.engine !== "" || f.needs_review || f.cleaning_activated;

  return (
    <div className="page-content history-page">
      <div className="page-tools history-tools">
        <span className="tools-hint">
          {!getAdminKey() && config.admin_protegido ? "Se o servidor tiver chave de administrador, informe-a no botão Admin do topo." : ""}
        </span>
        <button className="secondary-button" onClick={exportZip} title="Zip com as fotos corrigidas por pessoas, em pastas por classe, para retreinar os modelos">
          <Download size={16} aria-hidden /> Exportar fotos revisadas (retreino)
        </button>
      </div>
      {exportMsg && <p role="alert" className="alert warn">{exportMsg}</p>}

      <section className="card filters-card">
        <div className="filter-group" role="group" aria-label="Filtros">
          <Filter size={16} aria-hidden />
          <span>Filtros:</span>
          {LABELS.map((l) => <button key={l} className={f.labels.includes(l) ? "active" : ""} aria-pressed={f.labels.includes(l)} onClick={() => toggle(l)}>{l}</button>)}
          {(["esp32", "server"] as const).map((e) => (
            <button key={e} className={f.engine === e ? "active" : ""} aria-pressed={f.engine === e} onClick={() => setF((p) => ({ ...p, engine: p.engine === e ? "" : e }))}>{ENGINE_NAME[e]}</button>
          ))}
          <button className={f.needs_review ? "active" : ""} aria-pressed={f.needs_review} onClick={() => setF((p) => ({ ...p, needs_review: !p.needs_review }))}>Para revisar</button>
          <button className={f.cleaning_activated ? "active" : ""} aria-pressed={f.cleaning_activated} onClick={() => setF((p) => ({ ...p, cleaning_activated: !p.cleaning_activated }))}><Droplets size={14} aria-hidden /> Bomba acionada</button>
        </div>
      </section>

      <section className="card history-table-card">
        <div className="history-summary">
          <div>
            <h2>{filtered ? "Análises filtradas" : "Todas as análises"}</h2>
            <p>{total} análise(s)</p>
          </div>
          {review > 0 && <span><i /> {review} aguardam revisão</span>}
        </div>
        {err && <p role="alert" className="alert error table-alert">{err}</p>}
        {!loading && items.length === 0 && !err ? (
          <EmptyState icon={Search} title="Nenhuma análise encontrada" text={filtered ? "Tente remover ou alterar os filtros aplicados." : "Ainda não há análises. Envie a primeira foto na aba Analisar."} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>ANÁLISE</th><th>DATA E HORA</th><th>CLASSIFICAÇÃO FINAL</th><th>CONFIANÇA</th><th>MECANISMO</th><th>REVISÃO</th><th>BOMBA</th><th />
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id} data-testid="analysis-card" tabIndex={0} onClick={() => setOpen(a)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(a); } }}>
                    <td>
                      <div className="table-analysis">
                        <img src={a.image_url} alt={`Foto ${a.id}: ${a.final_label}`} loading="lazy" />
                        <strong>#{a.id}</strong>
                      </div>
                    </td>
                    <td><strong>{dayLabel(a.created_at)}</strong><small>{hourLabel(a.created_at)}</small></td>
                    <td>
                      <LabelBadge label={a.final_label} />
                      {a.human_label && <span className="human-mark" title={`${ENGINE_NAME[a.engine ?? "esp32"]} disse ${a.classification}`}>Corrigida</span>}
                    </td>
                    <td>
                      <div className="confidence-cell">
                        <strong className={a.low_confidence ? "low" : ""}>{pct(a.confidence)}</strong>
                        <i><em style={{ width: pct(a.confidence) }} /></i>
                      </div>
                    </td>
                    <td><EngineName engine={a.engine} /></td>
                    <td>
                      {a.human_label ? <span className="reviewed"><Check size={14} aria-hidden /> Revisada</span>
                        : a.needs_review ? <span className="pending"><CircleAlert size={14} aria-hidden /> Pendente</span>
                        : <span className="na">—</span>}
                    </td>
                    <td>
                      {a.engine === "server" ? <span className="na">—</span>
                        : a.cleaning_activated ? <span className="pump-on"><Droplets size={14} aria-hidden /> Acionada</span>
                        : <span className="na">Não acionada</span>}
                    </td>
                    <td><ChevronRight size={17} className="row-chevron" aria-hidden /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {loading && items.length === 0 && <p className="loading-line">Carregando…</p>}
        <div className="pagination">
          <span>Mostrando {items.length} de {total}</span>
          {items.length < total && <button className="load-more" disabled={loading} onClick={() => load(items.length)}>Carregar mais</button>}
        </div>
      </section>
      {open && <DetailModal a={open} config={config} onClose={() => setOpen(null)} onChanged={() => { onChanged(); void load(0); }} />}
    </div>
  );
}
