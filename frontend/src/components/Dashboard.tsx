import { Activity, Check, ChevronRight, CircleAlert, FileImage, ShieldCheck, Upload } from "lucide-react";
import { useEffect, useState, type ElementType } from "react";
import { api } from "../api";
import { dayLabel, hourLabel, LABEL_STYLE, pct, pct1 } from "../lib/format";
import type { Analysis, Config, Label, Stats } from "../types";
import { LABELS } from "../types";
import { DetailModal } from "./DetailModal";
import { EmptyState } from "./EmptyState";
import { EngineName } from "./EngineName";
import { LabelBadge } from "./LabelBadge";
import { WeatherCard } from "./WeatherCard";

const NF = new Intl.NumberFormat("pt-BR");
const share = (n: number, total: number) => (total ? `${((n / total) * 100).toFixed(1).replace(".", ",")}% do total` : "—");
const TONE: Record<Label, string> = { LIMPO: "clean", MODERADO: "moderate", SEVERO: "severe" };

function MetricCard({ title, value, detail, tone, icon: Icon, spark }: { title: string; value: string; detail: string; tone: string; icon: ElementType; spark?: number[] }) {
  const max = Math.max(1, ...(spark ?? [0]));
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={19} aria-hidden /></div>
      <div className="metric-main"><p>{title}</p><strong>{value}</strong><small>{detail}</small></div>
      {spark && (
        <div className={`metric-spark ${tone}`} aria-hidden>
          {spark.map((v, i) => <span key={i} style={{ height: `${Math.max(12, (v / max) * 100)}%` }} />)}
        </div>
      )}
    </div>
  );
}

function Donut({ s }: { s: Stats }) {
  let acc = 0;
  const parts = LABELS.map((l) => {
    const from = (acc / s.total) * 100;
    acc += s.por_rotulo[l] ?? 0;
    return `${LABEL_STYLE[l].solid} ${from}% ${(acc / s.total) * 100}%`;
  });
  return (
    <div className="donut-wrap">
      <div className="donut" style={{ background: `conic-gradient(${parts.join(",")})` }} role="img"
        aria-label={LABELS.map((l) => `${l}: ${s.por_rotulo[l] ?? 0}`).join(", ")}>
        <div><strong>{NF.format(s.total)}</strong><span>Total</span></div>
      </div>
      <div className="legend-list">
        {LABELS.map((l) => (
          <div key={l}><i className={TONE[l]} /><span>{l.charAt(0) + l.slice(1).toLowerCase()}</span><strong>{NF.format(s.por_rotulo[l] ?? 0)}</strong><small>{pct1((s.por_rotulo[l] ?? 0) / s.total)}</small></div>
        ))}
      </div>
    </div>
  );
}

function Trend({ s }: { s: Stats }) {
  const days = s.serie_diaria;
  const totals = days.map((d) => LABELS.reduce((n, l) => n + (d[l] ?? 0), 0));
  const top = Math.max(4, ...totals);
  const W = 520, H = 150;
  const x = (i: number) => (days.length > 1 ? (i * W) / (days.length - 1) : W / 2);
  const y = (v: number) => H - (v / top) * (H - 14);
  const pts = totals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const fmt = (iso: string) => new Date(iso + (iso.length <= 10 ? "T12:00:00" : "")).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "");
  const ticks = days.length ? [0, Math.floor((days.length - 1) / 2), days.length - 1].filter((v, i, a) => a.indexOf(v) === i) : [];
  return (
    <div className="trend-chart">
      <div className="y-axis">{[top, Math.round(top * 0.75), Math.round(top / 2), Math.round(top / 4), 0].map((v, i) => <span key={i}>{v}</span>)}</div>
      <svg viewBox={`0 0 ${W} 160`} preserveAspectRatio="none" role="img" aria-label="Análises por dia">
        <defs><linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1596dd" stopOpacity=".24" /><stop offset="1" stopColor="#1596dd" stopOpacity="0" /></linearGradient></defs>
        {[10, 45, 80, 115, 150].map((v) => <line key={v} x1="0" x2={W} y1={v} y2={v} stroke="#e8eef3" strokeWidth="1" />)}
        {days.length > 0 && <>
          <polygon points={`0,160 ${pts} ${W},160`} fill="url(#area)" />
          <polyline points={pts} fill="none" stroke="#178fd0" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </>}
      </svg>
      <div className="x-axis">{ticks.map((i) => <span key={i}>{fmt(days[i].dia)}</span>)}</div>
    </div>
  );
}

export function Dashboard({ config, refreshKey, onAnalyze, onOpenHistory, onChanged }: { config: Config; refreshKey: number; onAnalyze: () => void; onOpenHistory: () => void; onChanged: () => void }) {
  const [s, setS] = useState<Stats | null>(null);
  const [recent, setRecent] = useState<Analysis[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<Analysis | null>(null);

  useEffect(() => {
    setErr(null);
    api.stats().then(setS).catch((e: Error) => setErr(e.message));
    api.list({ engine: "", labels: [], needs_review: false, cleaning_activated: false }, 4, 0).then((r) => setRecent(r.itens)).catch(() => setRecent([]));
  }, [refreshKey]);

  const series = (l: Label) => (s?.serie_diaria ?? []).slice(-6).map((d) => d[l] ?? 0);
  const totalSeries = (s?.serie_diaria ?? []).slice(-6).map((d) => LABELS.reduce((n, l) => n + (d[l] ?? 0), 0));
  const periodo = s?.serie_diaria.reduce((n, d) => n + LABELS.reduce((m, l) => m + (d[l] ?? 0), 0), 0) ?? 0;

  return (
    <div className="page-content dashboard-page">
      <div className="page-tools">
        <span className="tools-hint">Resumo de todas as análises registradas</span>
        <button className="primary-button" onClick={onAnalyze}><Upload size={17} aria-hidden /> Nova análise</button>
      </div>
      {err && <p role="alert" className="alert error">{err}</p>}
      {!s && !err && <p className="loading-line">Carregando…</p>}
      {s && s.total === 0 && (
        <>
          <div className="card"><EmptyState title="Nenhuma análise ainda" text="Envie a primeira foto de um painel na aba Analisar para ver o painel de controle." /></div>
          <WeatherCard variant="strip" />
        </>
      )}
      {s && s.total > 0 && (
        <>
          <section className="metrics-grid">
            <MetricCard title="Imagens analisadas" value={NF.format(s.total)} detail={s.ultima_analise ? `Última: ${dayLabel(s.ultima_analise)}, ${hourLabel(s.ultima_analise)}` : "—"} tone="blue" icon={FileImage} spark={totalSeries} />
            <MetricCard title="Painéis limpos" value={NF.format(s.por_rotulo.LIMPO ?? 0)} detail={share(s.por_rotulo.LIMPO ?? 0, s.total)} tone="green" icon={Check} spark={series("LIMPO")} />
            <MetricCard title="Sujeira moderada" value={NF.format(s.por_rotulo.MODERADO ?? 0)} detail={share(s.por_rotulo.MODERADO ?? 0, s.total)} tone="amber" icon={CircleAlert} spark={series("MODERADO")} />
            <MetricCard title="Sujeira severa" value={NF.format(s.por_rotulo.SEVERO ?? 0)} detail={share(s.por_rotulo.SEVERO ?? 0, s.total)} tone="red" icon={Activity} spark={series("SEVERO")} />
            <MetricCard title="Aguardando revisão" value={NF.format(s.para_revisao)} detail={`Confiança abaixo de ${pct(config.low_confidence_threshold)}`} tone="purple" icon={ShieldCheck} />
          </section>
          <section className="dashboard-grid">
            <div className="card chart-card">
              <div className="card-head"><div><h2>Distribuição das classificações</h2><p>Classificação final, considerando revisões humanas</p></div></div>
              <Donut s={s} />
            </div>
            <div className="card chart-card trend-card">
              <div className="card-head"><div><h2>Análises ao longo do tempo</h2><p>Volume diário de imagens processadas</p></div></div>
              <div className="trend-kpi"><strong>{NF.format(periodo)}</strong><span>análises no período</span></div>
              <Trend s={s} />
            </div>
            <div className="card chart-card engine-card">
              <div className="card-head"><div><h2>Processamento por mecanismo</h2><p>Quem classificou cada foto</p></div></div>
              <div className="engine-totals">
                {(["esp32", "server"] as const).map((e) => (
                  <div key={e}><span><EngineName engine={e} /></span><strong>{NF.format(s.por_motor[e] ?? 0)}</strong><small>{pct1((s.por_motor[e] ?? 0) / s.total)}</small></div>
                ))}
              </div>
              <div className="split-bar" aria-hidden><i className="esp" style={{ width: `${((s.por_motor.esp32 ?? 0) / s.total) * 100}%` }} /><i className="srv" style={{ width: `${((s.por_motor.server ?? 0) / s.total) * 100}%` }} /></div>
              <dl className="kv-list">
                <div><dt>Limpezas acionadas</dt><dd>{s.limpezas_acionadas}</dd></div>
                <div><dt>Tempo total de bomba</dt><dd>{(s.tempo_total_bomba_ms / 1000).toFixed(0)} s</dd></div>
                <div><dt>Confiança média</dt><dd>{pct1(s.confianca_media)}</dd></div>
                <div><dt>Inferência média</dt><dd>{s.inferencia_media_ms == null ? "—" : `${Math.round(s.inferencia_media_ms)} ms`}</dd></div>
                <div><dt>Revisadas por humano</dt><dd>{s.revisadas}</dd></div>
              </dl>
            </div>
            <WeatherCard variant="full" />
            <div className="card recent-card">
              <div className="card-head">
                <div><h2>Últimas análises</h2><p>Resultados mais recentes do sistema</p></div>
                <button className="text-button" onClick={onOpenHistory}>Ver histórico <ChevronRight size={15} aria-hidden /></button>
              </div>
              <div className="recent-list">
                {recent.map((a) => (
                  <button className="recent-row" key={a.id} onClick={() => setOpen(a)}>
                    <img src={a.image_url} alt={`Foto ${a.id}`} loading="lazy" />
                    <div className="analysis-name"><strong>#{a.id}</strong><small>{dayLabel(a.created_at)}, {hourLabel(a.created_at)}</small></div>
                    <LabelBadge label={a.final_label} />
                    <EngineName engine={a.engine} />
                    <strong className="confidence">{pct(a.confidence)}</strong>
                    <ChevronRight size={17} className="row-chevron" aria-hidden />
                  </button>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
      {open && <DetailModal a={open} config={config} onClose={() => setOpen(null)} onChanged={onChanged} />}
    </div>
  );
}
