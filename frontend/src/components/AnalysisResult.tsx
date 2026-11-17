import { Check, Droplets } from "lucide-react";
import { LABEL_STYLE, duration, labelText, pct, pct1, seconds, when } from "../lib/format";
import type { Analysis, Config } from "../types";
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

/** Limiar de decisão do modelo que fez a análise (hoje só o do servidor é conhecido pelo backend). */
export function decisionThreshold(a: Analysis, config?: Config): number | null {
  return a.engine === "server" ? config?.engines.server.limiar ?? null : null;
}

/** Barras de probabilidade das duas classes. Com limiar conhecido, marca o ponto a partir do qual vira "Precisa limpar":
 *  com limiar baixo (ex.: 19%), "Precisa limpar" pode vencer com a barra menor, e a marca mostra o porquê. */
export function Probabilities({ a, config }: { a: Analysis; config?: Config }) {
  if (!a.probs) return null;
  const probs = a.probs;
  const limiar = decisionThreshold(a, config);
  return (
    <div className="probabilities" aria-label="Probabilidades por classe">
      <span>Probabilidades por classe</span>
      {LABELS.filter((l) => l in probs).map((l) => (
        <div key={l}>
          <b>{labelText(l)}</b>
          <i>
            <em className={l.toLowerCase()} style={{ width: pct(probs[l] ?? 0) }} />
            {l === "SEVERO" && limiar != null && <span className="threshold-mark" style={{ left: pct(limiar) }} aria-hidden />}
          </i>
          <strong>{pct1(probs[l] ?? 0)}</strong>
        </div>
      ))}
      {limiar != null && (
        <small className="threshold-note">
          “{LABEL_STYLE.SEVERO.text}” a partir de {pct1(limiar)} (limiar do modelo, marcado na barra).
          {config?.engines.server.revisao_ate != null && config.engines.server.revisao_ate > limiar &&
            ` Entre ${pct1(limiar)} e ${pct1(config.engines.server.revisao_ate)} o resultado vai para revisão humana.`}
        </small>
      )}
    </div>
  );
}

/** Aviso de revisão: no servidor ele vem da faixa de dúvida; no ESP32, da confiança baixa. */
export function reviewMessage(a: Analysis): string {
  return a.engine === "server"
    ? "Resultado na faixa de dúvida do modelo: peça uma revisão humana antes de agir."
    : "Confiança baixa: peça uma revisão humana antes de agir.";
}

export function AnalysisResult({ a, config, blocked = false }: { a: Analysis; config?: Config; blocked?: boolean }) {
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
          <div className={`big-label ${cls.toLowerCase()}`}><span aria-hidden />{labelText(cls)}</div>
          <p>{LABEL_STYLE[cls]?.desc ?? cls}.</p>
          {a.needs_review && <p className="alert warn">{reviewMessage(a)}</p>}
          <div className="confidence-block">
            <div>
              <span>Confiança do modelo</span>
              <strong>{pct1(a.confidence)}</strong>
            </div>
            <div className="progress"><i style={{ width: pct(a.confidence) }} /></div>
            <small>Confiança representa a certeza do modelo, não o percentual de sujeira.</small>
          </div>
          <Probabilities a={a} config={config} />
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
      <p className="sr-only">{ENGINE_NAME[a.engine ?? "esp32"]} classificou como “{labelText(cls)}”.</p>
    </section>
  );
}
