import { Check, Droplets } from "lucide-react";
import { LABEL_STYLE, duration, pct, pct1, seconds, when } from "../lib/format";
import type { Analysis } from "../types";
import { ENGINE_NAME, LABELS } from "../types";
import { EngineName } from "./EngineName";

/** O que a bomba fez, em palavras. Usado na tela de resultado e no modal. */
export function PumpResult({ a, blocked = false }: { a: Analysis; blocked?: boolean }) {
  const title = a.cleaning_activated ? `Bomba acionada por ${seconds(a.pump_duration_ms)}` : a.engine === "server" ? "Análise do servidor: sem bomba" : "Bomba não acionada";
  return (
    <div className={`pump-result ${a.cleaning_activated ? "active" : ""}`}>
      <Droplets size={18} aria-hidden />
      <div>
        <strong>{title}</strong>
        {a.pump_reason && <span>{a.pump_reason}</span>}
        {blocked && <span className="pump-blocked">A bomba ficou bloqueada: informe a chave de administrador (botão Admin, no topo).</span>}
      </div>
    </div>
  );
}

/** Barras de probabilidade: só as classes que esse modelo tem (o do ESP32 pode ter 2). */
export function Probabilities({ a }: { a: Analysis }) {
  if (!a.probs) return null;
  const probs = a.probs;
  return (
    <div className="probabilities" aria-label="Probabilidades por classe">
      <span>Probabilidades por classe</span>
      {LABELS.filter((l) => l in probs).map((l) => (
        <div key={l}>
          <b>{l}</b>
          <i><em className={l.toLowerCase()} style={{ width: pct(probs[l] ?? 0) }} /></i>
          <strong>{pct1(probs[l] ?? 0)}</strong>
        </div>
      ))}
    </div>
  );
}

export function AnalysisResult({ a, blocked = false }: { a: Analysis; blocked?: boolean }) {
  const cls = a.classification;
  return (
    <section className="result-section" aria-label="Resultado" aria-live="polite">
      <div className="section-title">
        <div>
          <span className="success-check"><Check size={17} aria-hidden /></span>
          <h2>Análise concluída</h2>
        </div>
        <small>{when(a.created_at)}</small>
      </div>
      <div className="result-grid" data-testid="result">
        <div className="result-image">
          <img src={a.image_url} alt="Imagem analisada" />
          <span>Imagem processada</span>
        </div>
        <div className="result-main">
          <span className="eyebrow">RESULTADO DO MODELO</span>
          <div className={`big-label ${cls.toLowerCase()}`}><span aria-hidden />{cls}</div>
          <p>{LABEL_STYLE[cls].desc}.</p>
          {a.needs_review && <p className="alert warn">Confiança baixa: peça uma revisão humana antes de agir.</p>}
          <div className="confidence-block">
            <div>
              <span>Confiança do modelo</span>
              <strong>{pct1(a.confidence)}</strong>
            </div>
            <div className="progress"><i style={{ width: pct(a.confidence) }} /></div>
            <small>Confiança representa a certeza do modelo, não o percentual de sujeira.</small>
          </div>
          <Probabilities a={a} />
        </div>
        <div className="technical-panel">
          <h3>Detalhes técnicos</h3>
          <dl>
            <div><dt>Analisado por</dt><dd><EngineName engine={a.engine} /></dd></div>
            <div><dt>Inferência</dt><dd>{a.inference_ms != null ? `${a.inference_ms} ms` : "—"}</dd></div>
            <div><dt>{a.engine === "server" ? "Tempo total" : "Ida e volta total"}</dt><dd>{duration(a.round_trip_ms)}</dd></div>
            <div><dt>Modelo</dt><dd>{a.model_version ?? "—"}</dd></div>
            <div><dt>Imagem</dt><dd>{a.width} × {a.height} px</dd></div>
          </dl>
          <PumpResult a={a} blocked={blocked} />
        </div>
      </div>
      <p className="sr-only">{ENGINE_NAME[a.engine ?? "esp32"]} classificou como {cls}.</p>
    </section>
  );
}
