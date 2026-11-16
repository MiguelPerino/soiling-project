import { Cloud, CloudRain, CloudSun, Droplets, RefreshCw, Sun } from "lucide-react";
import { useCallback, useEffect, useState, type ElementType } from "react";
import { api } from "../api";
import type { WeatherAdvice } from "../types";

const ICON: Record<string, ElementType> = { limpar_agora: Sun, avaliar: CloudSun, adiar: CloudRain };

/** Recomendação de chuva ANTES de limpar (Open-Meteo). Só informa; nunca liga nem bloqueia a bomba. */
function useWeather() {
  const [w, setW] = useState<WeatherAdvice | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    setBusy(true);
    api.weather().then(setW).catch(() => setW(null)).finally(() => setBusy(false));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(() => { if (!document.hidden) load(); }, 30 * 60 * 1000);
    return () => clearInterval(t);
  }, [load]);
  return { w, busy, load };
}

function Facts({ w }: { w: WeatherAdvice }) {
  if (!w.disponivel) return null;
  return (
    <div className="weather-facts">
      <span><b>ÚLTIMAS 24 H</b><strong>{w.chuva_24h_passadas_mm} mm</strong></span>
      <span><b>PRÓXIMAS 24 H</b><strong>{w.chuva_24h_proximas_mm} mm</strong></span>
      {w.prob_max_24h != null && <span><b>CHANCE MÁXIMA</b><strong>{w.prob_max_24h}%</strong></span>}
    </div>
  );
}

function Credit({ w }: { w: WeatherAdvice }) {
  return (
    <>
      {w.aviso}{w.limiares ? ` Fraca ≥ ${w.limiares.fraca_mm} mm, forte ≥ ${w.limiares.forte_mm} mm em 24 h.` : ""}{" "}
      <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">{w.fonte}</a>
    </>
  );
}

export function WeatherCard({ variant = "full" }: { variant?: "full" | "strip" }) {
  const { w, busy, load } = useWeather();

  if (!w) {
    return (
      <section className={variant === "full" ? "card weather-off" : "weather-strip idle"} aria-label="Recomendação de chuva">
        <Cloud size={18} aria-hidden /> {busy ? "Consultando a previsão de chuva…" : "Recomendação de chuva indisponível."}
      </section>
    );
  }
  const Icon = ICON[w.nivel] ?? Cloud;

  if (variant === "strip") {
    return (
      <section aria-label="Recomendação de chuva" data-testid="weather" className={`weather-strip ${w.nivel}`}>
        <div className="weather-strip-icon"><Icon size={26} aria-hidden /></div>
        <div className="weather-strip-text">
          <span className="eyebrow">ANTES DE LIMPAR: CHUVA</span>
          <h2>{w.titulo}</h2>
          <p>{w.mensagem}</p>
          {w.observacoes.map((o) => <p key={o} className="obs">• {o}</p>)}
          {w.disponivel && (
            <p className="obs">
              Últimas 24 h: <strong>{w.chuva_24h_passadas_mm} mm</strong> · Próximas 24 h: <strong>{w.chuva_24h_proximas_mm} mm</strong>
              {w.prob_max_24h != null && <> · chance máxima {w.prob_max_24h}%</>}
              {w.desatualizado && <> · <em>dados desatualizados (sem conexão)</em></>}
            </p>
          )}
          <small><Credit w={w} /></small>
        </div>
        <button className="secondary-button" onClick={load} disabled={busy}><RefreshCw size={15} className={busy ? "spin" : ""} aria-hidden /> Atualizar</button>
      </section>
    );
  }

  return (
    <section aria-label="Recomendação de chuva" data-testid="weather" className={`weather-card card ${w.nivel}`}>
      <div className="weather-visual">
        {w.nivel !== "adiar" && <div className="sun-shape" />}
        <Icon size={50} aria-hidden />
      </div>
      <div className="weather-now">
        <div>
          <span>ANTES DE LIMPAR: CHUVA</span>
          <strong className="weather-title">{w.titulo}</strong>
          <p>{w.mensagem}</p>
        </div>
      </div>
      <div className="weather-divider" />
      <Facts w={w} />
      {(w.observacoes.length > 0 || w.desatualizado) && (
        <div className="weather-tip">
          <Droplets size={18} aria-hidden />
          <p>
            {w.observacoes.map((o) => <span key={o}>{o}</span>)}
            {w.desatualizado && <span><em>Dados desatualizados (sem conexão).</em></span>}
          </p>
        </div>
      )}
      <small className="source-note"><Credit w={w} /></small>
      <button className="weather-refresh" onClick={load} disabled={busy} aria-label="Atualizar previsão"><RefreshCw size={14} className={busy ? "spin" : ""} /></button>
    </section>
  );
}
