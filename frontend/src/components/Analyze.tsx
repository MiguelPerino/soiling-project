import { Check, Cpu, FileImage, Gauge, ImageUp, RefreshCw, Server, Sparkles, Trash2, Wifi, Zap } from "lucide-react";
import { useEffect, useRef, useState, type DragEvent } from "react";
import { api, ApiError } from "../api";
import { prepareImage } from "../lib/image";
import type { Analysis, Config, Engine } from "../types";
import { ENGINE_NAME } from "../types";
import { AnalysisResult } from "./AnalysisResult";
import { WeatherCard } from "./WeatherCard";

type Phase = "idle" | "preparing" | "analyzing";

export function Analyze({ config, onDone }: { config: Config; onDone: () => void }) {
  const [file, setFile] = useState<File | Blob | null>(null);
  const [name, setName] = useState("foto.jpg");
  const [preview, setPreview] = useState<string | null>(null);
  const [engine, setEngine] = useState<Engine>(config.engines.esp32.disponivel || !config.engines.server.disponivel ? "esp32" : "server");
  const [pump, setPump] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const u = URL.createObjectURL(file);
    setPreview(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const choose = (f: File | undefined) => {
    if (!f) return;
    setFile(f); setName(f.name || "foto.jpg"); setResult(null); setError(null);
  };
  const clear = () => { setFile(null); setResult(null); setError(null); };

  const drop = {
    onDragOver: (e: DragEvent) => { e.preventDefault(); setDragging(true); },
    onDragLeave: () => setDragging(false),
    onDrop: (e: DragEvent) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]); },
  };

  const send = async () => {
    if (!file) return;
    setError(null); setResult(null);
    try {
      setPhase("preparing");
      const small = await prepareImage(file, config.upload_max_side, config.jpeg_quality);
      setPhase("analyzing");
      const r = await api.analyze(small, name, engine === "esp32" && pump, engine);
      setResult(r.analise); setBlocked(r.bomba_bloqueada_por_falta_de_chave);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Erro inesperado.");
    } finally {
      setPhase("idle");
    }
  };

  const busy = phase !== "idle";
  const ready = !!file && config.engines[engine].disponivel;
  const sizes = (["esp32", "server"] as const).filter((e) => config.engines[e].disponivel && config.engines[e].input_size)
    .map((e) => `${ENGINE_NAME[e]} ${config.engines[e].input_size} px`).join(" · ");

  return (
    <div className="page-content analyze-page">
      {config.weather && <div className="weather-slot"><WeatherCard variant="strip" /></div>}
      <div className="analyze-layout">
        <section className="card upload-card" aria-label="Enviar foto">
          <div className="step-title">
            <span>1</span>
            <div>
              <h2>Escolha a foto do painel</h2>
              <p>Envie uma foto nítida do painel solar.</p>
            </div>
          </div>
          {!preview ? (
            <button type="button" className={`drop-zone ${dragging ? "dragging" : ""}`} onClick={() => input.current?.click()} {...drop}>
              <div className="upload-icon"><ImageUp size={27} aria-hidden /></div>
              <strong>Arraste e solte sua imagem aqui</strong>
              <span>ou clique para tirar uma foto / escolher um arquivo</span>
              <em>JPG, PNG ou WEBP • reduzida a {config.upload_max_side} px no navegador</em>
            </button>
          ) : (
            <div className="file-preview" {...drop}>
              <img src={preview} alt="Pré-visualização da foto escolhida" />
              <div className="file-overlay"><span><FileImage size={16} aria-hidden /> Pré-visualização</span></div>
              <div className="file-meta">
                <div>
                  <strong>{name}</strong>
                  <small>{file ? (file.size / 1024 / 1024).toFixed(2) : "0.00"} MB • Imagem pronta para envio</small>
                </div>
                <button type="button" onClick={() => input.current?.click()} disabled={busy}><RefreshCw size={16} aria-hidden /> Substituir</button>
                <button type="button" className="remove" onClick={clear} disabled={busy} aria-label="Remover imagem"><Trash2 size={16} /></button>
              </div>
            </div>
          )}
          <input ref={input} data-testid="file-input" type="file" accept="image/*" capture="environment" hidden aria-label="Escolher foto"
            onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
        </section>

        <section className="card engine-select-card" aria-label="Onde analisar">
          <div className="step-title">
            <span>2</span>
            <div>
              <h2>Onde analisar</h2>
              <p>A disponibilidade é informada pela API.</p>
            </div>
          </div>
          <fieldset className="engine-options" disabled={busy}>
            <legend className="sr-only">Onde analisar</legend>
            {(["esp32", "server"] as const).map((e) => {
              const info = config.engines[e];
              return (
                <label key={e} className={`engine-option ${engine === e ? "selected" : ""} ${info.disponivel ? "" : "off"}`}>
                  <input type="radio" name="engine" value={e} checked={engine === e} disabled={!info.disponivel} onChange={() => setEngine(e)} />
                  <div className={`engine-option-icon ${e === "server" ? "server" : ""}`}>{e === "esp32" ? <Cpu size={24} aria-hidden /> : <Server size={24} aria-hidden />}</div>
                  <div>
                    <span className={`available ${info.disponivel ? "" : "off"}`}><i /> {info.disponivel ? "DISPONÍVEL" : "INDISPONÍVEL"}</span>
                    <strong>{e === "esp32" ? "ESP32, na hora" : "Modelo grande, no servidor"}</strong>
                    <p>
                      {info.disponivel
                        ? e === "esp32" ? "Classifica e pode acionar a bomba." : `Análise mais robusta${info.versao ? ` (${info.versao})` : ""}. Não aciona a bomba.`
                        : `Indisponível${info.motivo ? `: ${info.motivo}` : ""}`}
                    </p>
                    <small>{e === "esp32" ? <><Zap size={14} aria-hidden /> Resposta rápida</> : <><Gauge size={14} aria-hidden /> Análise detalhada</>}</small>
                  </div>
                  <span className="radio" aria-hidden>{engine === e && <i />}</span>
                </label>
              );
            })}
          </fieldset>
          {engine === "esp32" && (
            <label className="pump-toggle">
              <input type="checkbox" checked={pump} onChange={(e) => setPump(e.target.checked)} disabled={busy} />
              <span className="box" aria-hidden><Check size={14} /></span>
              <span>Permitir acionar a bomba (só se o resultado for “Precisa limpar”)</span>
            </label>
          )}
          <div className="api-note">
            <Wifi size={15} aria-hidden />
            <span>Modos atualizados pela API</span>
            {sizes && <strong>Entrada: {sizes}</strong>}
          </div>
        </section>

        <section className="action-panel" aria-label="Analisar">
          <div>
            <span className={`ready-dot ${ready ? "ready" : ""}`} />
            <p>
              <strong>{busy ? "Analisando…" : ready ? "Tudo pronto para analisar" : file ? "Modo indisponível" : "Aguardando uma imagem"}</strong>
              <span>
                {phase === "analyzing" ? `Aguardando o ${ENGINE_NAME[engine]}…`
                  : file ? `A imagem será enviada ao ${ENGINE_NAME[engine]}. Ela é reduzida a no máximo ${config.upload_max_side} px no seu navegador.`
                  : "Selecione um arquivo para continuar."}
              </span>
            </p>
          </div>
          <button className="analyze-button" disabled={!file || busy || !config.engines[engine].disponivel} onClick={send}>
            {phase === "preparing" ? <><RefreshCw className="spin" size={18} aria-hidden /> Preparando a imagem…</>
              : phase === "analyzing" ? <><RefreshCw className="spin" size={18} aria-hidden /> {ENGINE_NAME[engine]} analisando…</>
              : <><Sparkles size={18} aria-hidden /> Iniciar classificação</>}
          </button>
          {busy && <div className="indeterminate"><i /></div>}
        </section>
      </div>
      {error && <p role="alert" className="alert error">{error}</p>}
      {result && <AnalysisResult a={result} config={config} blocked={blocked} />}
    </div>
  );
}
