import { KeyRound, Menu, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, getAdminKey } from "./api";
import type { Config, Stats } from "./types";
import { AdminPopover } from "./components/AdminKey";
import { Analyze } from "./components/Analyze";
import { Assistant } from "./components/Assistant";
import { Dashboard } from "./components/Dashboard";
import { History } from "./components/History";
import { Sidebar, TABS, type Tab } from "./components/Sidebar";
import { StatusPill, useDeviceStatus } from "./components/StatusPill";

export default function App() {
  const [tab, setTab] = useState<Tab>("analisar");
  const [config, setConfig] = useState<Config | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [adminSet, setAdminSet] = useState(!!getAdminKey());
  const [review, setReview] = useState(0);
  const device = useDeviceStatus();
  const bump = useCallback(() => setRefresh((n) => n + 1), []);

  useEffect(() => { api.config().then(setConfig).catch((e: Error) => setErr(e.message)); }, []);
  // Só para o número no menu "Histórico" (análises aguardando revisão).
  useEffect(() => { api.stats().then((s: Stats) => setReview(s.para_revisao)).catch(() => undefined); }, [refresh]);

  const meta = TABS.find((t) => t.id === tab)!;
  return (
    <div className="app-shell">
      <Sidebar tab={tab} setTab={setTab} mobileOpen={mobileOpen} setMobileOpen={setMobileOpen} review={review} device={device}
        config={config} adminSet={adminSet} onAdmin={() => { setAdminOpen((v) => !v); setMobileOpen(false); }} />
      <main className="main-area">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Abrir menu"><Menu size={21} /></button>
          <div className="page-heading">
            <h1>{meta.title}</h1>
            <p>{meta.subtitle}</p>
          </div>
          <div className="top-actions">
            <StatusPill view={device} />
            {config?.admin_protegido && (
              <button className="admin-chip" onClick={() => setAdminOpen((v) => !v)} aria-expanded={adminOpen}>
                {adminSet ? <ShieldCheck size={17} aria-hidden /> : <KeyRound size={17} aria-hidden />}
                <span>{adminSet ? "Admin ativo" : "Admin"}</span>
              </button>
            )}
          </div>
        </header>
        {adminOpen && config?.admin_protegido && <AdminPopover onClose={() => setAdminOpen(false)} onSaved={() => setAdminSet(!!getAdminKey())} />}
        {err && <div className="page-content"><p role="alert" className="alert error">{err}</p></div>}
        {!config && !err && <div className="page-content"><p className="loading-line">Carregando…</p></div>}
        {config && tab === "painel" && <Dashboard config={config} refreshKey={refresh} onAnalyze={() => setTab("analisar")} onOpenHistory={() => setTab("historico")} onChanged={bump} />}
        {config && tab === "analisar" && <Analyze config={config} onDone={bump} />}
        {config && tab === "historico" && <History config={config} refreshKey={refresh} review={review} onChanged={bump} />}
        {config && tab === "assistente" && <Assistant config={config} onChanged={bump} />}
      </main>
    </div>
  );
}
