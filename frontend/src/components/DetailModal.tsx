import { Check, ChevronRight, RefreshCw, ShieldCheck, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api, ApiError, getAdminKey } from "../api";
import { prepareImage } from "../lib/image";
import { duration, labelText, pct, when } from "../lib/format";
import type { Analysis, Config, Label } from "../types";
import { ENGINE_NAME, LABELS } from "../types";
import { PumpResult, Probabilities, reviewMessage } from "./AnalysisResult";
import { EngineName } from "./EngineName";
import { LabelBadge } from "./LabelBadge";

export function DetailModal({ a, config, onClose, onChanged }: { a: Analysis; config: Config; onClose: () => void; onChanged: () => void }) {
  const [cur, setCur] = useState(a);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setMsg(null);
    try { await fn(); } catch (e) { setMsg(e instanceof ApiError ? e.message : "Erro inesperado."); } finally { setBusy(false); }
  };

  const relabel = (l: Label | null) => run(async () => { setCur(await api.relabel(cur.id, l)); onChanged(); });
  const remove = () => run(async () => {
    if (!window.confirm("Apagar esta análise e a imagem? Não dá para desfazer.")) return;
    await api.remove(cur.id); onChanged(); onClose();
  });
  // "Imagem de reserva": reenvia uma foto já guardada, sem câmera. Útil se a câmera falhar na apresentação.
  const reanalyze = () => run(async () => {
    const blob = await (await fetch(cur.image_url)).blob();
    const small = await prepareImage(blob, config.upload_max_side, config.jpeg_quality);
    const r = await api.analyze(small, cur.original_filename || "reanalise.jpg", false, cur.engine ?? "esp32");
    setCur(r.analise); onChanged();
    setMsg("Reanalisado (bomba desativada nesta repetição). Uma nova análise foi criada no histórico.");
  });

  return (
    <div className="modal-layer" role="dialog" aria-modal="true" aria-label={`Análise ${cur.id}`}>
      <button className="modal-scrim" onClick={onClose} aria-label="Fechar" />
      <div className="detail-modal">
        <div className="modal-head">
          <div>
            <span>DETALHES DA ANÁLISE</span>
            <h2>Análise #{cur.id}</h2>
            <p>{when(cur.created_at)}</p>
          </div>
          <button onClick={onClose} aria-label="Fechar janela"><X size={20} /></button>
        </div>
        <div className="modal-body">
          <div className="modal-image">
            <img src={cur.image_url} alt={`Foto da análise ${cur.id}`} />
            <span>{cur.width} × {cur.height} px</span>
          </div>
          <div className="modal-results" data-testid="result">
            <div className="modal-labels">
              <div>
                <span>RESULTADO ORIGINAL DO MODELO</span>
                <LabelBadge label={cur.classification} />
                <small>Confiança de {pct(cur.confidence)} · {ENGINE_NAME[cur.engine ?? "esp32"]}</small>
              </div>
              <ChevronRight size={20} aria-hidden />
              <div>
                <span>CLASSIFICAÇÃO FINAL</span>
                <LabelBadge label={cur.final_label} />
                <small>{cur.human_label ? "Corrigida por uma pessoa" : "Sem correção humana"}</small>
              </div>
            </div>
            {cur.needs_review && <p className="alert warn">{reviewMessage(cur)}</p>}
            <div className="modal-info-grid">
              <div><span>Mecanismo</span><strong><EngineName engine={cur.engine} /></strong></div>
              <div><span>Tempo de inferência</span><strong>{cur.inference_ms != null ? `${cur.inference_ms} ms` : "—"}</strong></div>
              <div><span>{cur.engine === "server" ? "Tempo total" : "Ida e volta total"}</span><strong>{duration(cur.round_trip_ms)}</strong></div>
              <div><span>Modelo</span><strong>{cur.model_version ?? "—"}</strong></div>
            </div>
            <Probabilities a={cur} config={config} />
            <PumpResult a={cur} />
            <div className="review-box">
              <div>
                <ShieldCheck size={18} aria-hidden />
                <div>
                  <h3>Revisão humana</h3>
                  <p>{getAdminKey() ? "A classificação corrigida prevalece nas estatísticas." : "Requer a chave de administrador, se o servidor tiver uma."}</p>
                </div>
              </div>
              <div className="label-choice" role="group" aria-label="Corrigir classificação">
                {LABELS.map((l) => (
                  <button key={l} className={cur.final_label === l && !!cur.human_label ? "active" : ""} aria-pressed={cur.final_label === l && !!cur.human_label} disabled={busy} onClick={() => relabel(l)}>
                    <span aria-hidden />{labelText(l)}
                  </button>
                ))}
              </div>
              {cur.human_label && <button className="text-button remove-fix" disabled={busy} onClick={() => relabel(null)}>Remover correção</button>}
            </div>
            {msg && <p role="alert" className="alert warn">{msg}</p>}
          </div>
        </div>
        <div className="modal-actions">
          <button className="danger-button" disabled={busy} onClick={remove}><Trash2 size={16} aria-hidden /> Apagar</button>
          <div>
            <button className="secondary-button" disabled={busy} onClick={reanalyze}><RefreshCw size={16} aria-hidden /> Reanalisar esta foto</button>
            <button className="primary-button" onClick={onClose}><Check size={16} aria-hidden /> Fechar</button>
          </div>
        </div>
      </div>
    </div>
  );
}
