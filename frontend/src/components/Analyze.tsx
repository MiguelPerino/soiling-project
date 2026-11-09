import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { prepareImage } from "../lib/image";
import { LABEL_STYLE, pct, seconds } from "../lib/format";
import type { Analysis, Config } from "../types";
import { LABELS } from "../types";
import { LabelBadge } from "./LabelBadge";
import { WeatherCard } from "./WeatherCard";

type Phase = "idle" | "preparing" | "analyzing";

export function Analyze({ config, onDone }: { config: Config; onDone: () => void }) {
  const [file, setFile] = useState<File | Blob | null>(null);
  const [name, setName] = useState("foto.jpg");
  const [preview, setPreview] = useState<string | null>(null);
  const [pump, setPump] = useState(true);
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [blocked, setBlocked] = useState(false);
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

  const send = async () => {
    if (!file) return;
    setError(null); setResult(null);
    try {
      setPhase("preparing");
      const small = await prepareImage(file, config.input_size, config.jpeg_quality);
      setPhase("analyzing");
      const r = await api.analyze(small, name, pump);
      setResult(r.analise); setBlocked(r.bomba_bloqueada_por_falta_de_chave);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Erro inesperado.");
    } finally {
      setPhase("idle");
    }
  };

  const busy = phase !== "idle";
  return (
    <div className="space-y-4">
    {config.weather && <WeatherCard />}
    <div className="grid gap-4 md:grid-cols-2">
      <section className="card space-y-3" aria-label="Enviar foto">
        <h2 className="text-lg font-semibold">1. Escolha a foto do painel</h2>
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); choose(e.dataTransfer.files[0]); }}
          className="flex min-h-[220px] items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-stone-300 bg-stone-100 dark:border-stone-700 dark:bg-stone-800"
        >
          {preview ? <img src={preview} alt="Pré-visualização da foto escolhida" className="max-h-72 w-full object-contain" />
            : <p className="px-4 text-center text-stone-500">Arraste uma imagem aqui, ou use os botões abaixo</p>}
        </div>
        <input ref={input} data-testid="file-input" type="file" accept="image/*" capture="environment" className="sr-only" id="file"
          onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
        <div className="flex flex-wrap gap-2">
          <label htmlFor="file" className="btn btn-ghost cursor-pointer">📷 Tirar foto / escolher arquivo</label>
        </div>
        <label className="flex min-h-[44px] items-center gap-3">
          <input type="checkbox" checked={pump} onChange={(e) => setPump(e.target.checked)} className="h-5 w-5 accent-amber-500" />
          <span>Permitir acionar a bomba (só se o resultado for SEVERO)</span>
        </label>
        <p className="text-xs text-stone-500">A foto será reduzida para {config.input_size}×{config.input_size} px no seu navegador antes do envio.</p>
        <button className="btn btn-primary w-full" disabled={!file || busy} onClick={send}>
          {phase === "preparing" ? "Preparando a imagem…" : phase === "analyzing" ? "ESP32 analisando…" : "2. Analisar"}
        </button>
        {error && <p role="alert" className="rounded-lg bg-red-100 p-3 text-sm text-red-900 dark:bg-red-950 dark:text-red-200">{error}</p>}
      </section>

      <section className="card" aria-label="Resultado" aria-live="polite">
        <h2 className="mb-3 text-lg font-semibold">Resultado</h2>
        {busy && <div className="flex items-center gap-3 py-10 text-stone-500"><span className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />{phase === "analyzing" ? "Aguardando o ESP32…" : "Preparando…"}</div>}
        {!busy && !result && <p className="py-10 text-stone-500">O resultado aparece aqui.</p>}
        {!busy && result && <ResultView a={result} blocked={blocked} />}
      </section>
    </div>
    </div>
  );
}

export function ResultView({ a, blocked = false }: { a: Analysis; blocked?: boolean }) {
  return (
    <div className="space-y-4" data-testid="result">
      <div className="flex flex-wrap items-center gap-3">
        <LabelBadge label={a.classification} big />
        <span className="text-lg">confiança <strong>{pct(a.confidence)}</strong></span>
      </div>
      <p className="text-stone-600 dark:text-stone-300">{LABEL_STYLE[a.classification].desc}.</p>
      {a.needs_review && <p className="rounded-lg bg-amber-100 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-200">Confiança baixa: peça uma revisão humana antes de agir.</p>}
      {a.probs && (
        <div className="space-y-1.5" aria-label="Probabilidades por classe">
          {LABELS.map((l) => (
            <div key={l} className="flex items-center gap-2 text-sm">
              <span className="w-24">{l}</span>
              <div className="h-3 flex-1 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
                <div className="h-full rounded-full" style={{ width: pct(a.probs?.[l] ?? 0), background: LABEL_STYLE[l].solid }} />
              </div>
              <span className="w-10 text-right tabular-nums">{pct(a.probs?.[l] ?? 0)}</span>
            </div>
          ))}
        </div>
      )}
      <div className={`rounded-xl p-3 ${a.cleaning_activated ? "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-100" : "bg-stone-100 dark:bg-stone-800"}`}>
        <p className="font-semibold">{a.cleaning_activated ? `💧 Bomba acionada por ${seconds(a.pump_duration_ms)}` : "Bomba não acionada"}</p>
        {a.pump_reason && <p className="text-sm">{a.pump_reason}</p>}
        {blocked && <p className="text-sm font-medium">A bomba ficou bloqueada: informe a chave de administrador (botão 🔒 no topo).</p>}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-stone-600 dark:text-stone-400">
        <dt>Inferência no ESP32</dt><dd className="text-right tabular-nums">{a.inference_ms ?? "—"} ms</dd>
        <dt>Ida e volta total</dt><dd className="text-right tabular-nums">{a.round_trip_ms ?? "—"} ms</dd>
        <dt>Modelo</dt><dd className="truncate text-right">{a.model_version ?? "—"}</dd>
      </dl>
    </div>
  );
}
