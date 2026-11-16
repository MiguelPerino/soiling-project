import { Bot, History, ImageUp, KeyRound, LayoutDashboard, MessageSquareText, Server, ShieldCheck, Wifi, WifiOff, X } from "lucide-react";
import type { ElementType } from "react";
import type { Config } from "../types";
import { describeDevice, type DeviceView } from "./StatusPill";

export const TABS = [
  { id: "painel", label: "Painel", icon: LayoutDashboard, title: "Visão geral", subtitle: "Acompanhe a operação e a saúde dos seus painéis." },
  { id: "analisar", label: "Analisar", icon: ImageUp, title: "Nova análise", subtitle: "Envie uma imagem para classificação inteligente." },
  { id: "historico", label: "Histórico", icon: History, title: "Histórico de análises", subtitle: "Consulte, revise e gerencie os resultados." },
  { id: "assistente", label: "Assistente", icon: MessageSquareText, title: "Assistente SolarEye", subtitle: "Consulte seus dados usando linguagem natural." },
] as const satisfies readonly { id: string; label: string; icon: ElementType; title: string; subtitle: string }[];
export type Tab = (typeof TABS)[number]["id"];

interface Props {
  tab: Tab;
  setTab: (t: Tab) => void;
  mobileOpen: boolean;
  setMobileOpen: (v: boolean) => void;
  review: number;
  device: DeviceView;
  config: Config | null;
  adminSet: boolean;
  onAdmin: () => void;
}

export function Sidebar({ tab, setTab, mobileOpen, setMobileOpen, review, device, config, adminSet, onAdmin }: Props) {
  const d = describeDevice(device);
  const big = config?.engines.server;
  return (
    <>
      {mobileOpen && <button className="scrim" aria-label="Fechar menu" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`} aria-label="Menu principal">
        <div className="brand">
          <div className="brand-mark"><img src="/assets/ml2-mark.png" alt="" /></div>
          <div>
            <strong>Solar<span>Eye</span></strong>
            <small>por ML2 Solutions</small>
          </div>
          <button className="close-mobile" onClick={() => setMobileOpen(false)} aria-label="Fechar menu"><X size={20} /></button>
        </div>
        <nav aria-label="Seções">
          <p className="nav-label">MONITORAMENTO</p>
          {TABS.map((t) => (
            <button key={t.id} aria-current={tab === t.id ? "page" : undefined} className={tab === t.id ? "active" : ""}
              onClick={() => { setTab(t.id); setMobileOpen(false); }}>
              <t.icon size={19} aria-hidden /> <span>{t.label}</span>
              {t.id === "historico" && review > 0 && <em title="Análises aguardando revisão" aria-label={`${review} aguardando revisão`}>{review}</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-system">
          <p className="nav-label">SISTEMA</p>
          <div className="system-row">
            <div className={`status-icon ${d.tone === "ok" ? "online" : ""}`}>{d.tone === "ok" ? <Wifi size={16} /> : <WifiOff size={16} />}</div>
            <div>
              <strong>{d.tone === "ok" ? "ESP32 conectado" : d.tone === "idle" ? "Verificando ESP32" : d.text.startsWith("ESP32") ? d.text : "Sem conexão"}</strong>
              <small>{d.detail}</small>
            </div>
            {d.tone === "ok" && <span className="online-dot" />}
          </div>
          {config && (
            <div className="system-row">
              <div className={`status-icon ${big?.disponivel ? "online" : ""}`}><Server size={16} /></div>
              <div>
                <strong>{big?.disponivel ? "Modelo grande ativo" : "Modelo grande indisponível"}</strong>
                <small>{big?.disponivel ? (big.versao ?? "ONNX no servidor") : (big?.motivo ?? "Sem modelo em models/server")}</small>
              </div>
              {big?.disponivel && <span className="online-dot" />}
            </div>
          )}
          {config && (
            <div className="system-row">
              <div className={`status-icon ${config.ia_gemini ? "online" : ""}`}><Bot size={16} /></div>
              <div>
                <strong>{config.ia_gemini ? "Assistente com IA" : "Assistente por regras"}</strong>
                <small>{config.ia_gemini ? "Gemini ativo" : "IA não configurada"}</small>
              </div>
            </div>
          )}
        </div>
        <div className="sidebar-bottom">
          {config?.admin_protegido && (
            <button className="admin-mini" onClick={onAdmin}>
              <KeyRound size={17} aria-hidden />
              <span>
                <strong>Modo administrador</strong>
                <small>{adminSet ? "Chave informada" : "Informe a chave"}</small>
              </span>
              {adminSet && <ShieldCheck size={17} className="verified" aria-hidden />}
            </button>
          )}
          <p>SolarEye <span>•</span> {device.lost ? "API fora do ar" : "API conectada"}</p>
        </div>
      </aside>
    </>
  );
}
