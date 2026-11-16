import { Wifi, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { DeviceStatus } from "../types";

export interface DeviceView { s: DeviceStatus | null; lost: boolean }

/** Pergunta a cada 5 s se o ESP32 está no ar. Um só lugar consulta; quem precisa do estado recebe por props. */
export function useDeviceStatus(): DeviceView {
  const [s, setS] = useState<DeviceStatus | null>(null);
  const [lost, setLost] = useState(false);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api.deviceStatus().then((v) => { if (alive) { setS(v); setLost(false); } }).catch(() => alive && setLost(true));
    tick();
    const t = setInterval(tick, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return { s, lost };
}

export type Tone = "ok" | "warn" | "bad" | "idle";

export function describeDevice({ s, lost }: DeviceView): { text: string; tone: Tone; detail: string } {
  if (lost) return { text: "servidor fora do ar", tone: "bad", detail: "A API não respondeu" };
  if (s && !s.configured) return { text: "ESP32 não configurado", tone: "warn", detail: "Defina ESP32_URL no backend" };
  if (s?.online) return { text: `ESP32 online · ${s.latency_ms} ms`, tone: "ok", detail: `Latência de ${s.latency_ms} ms` };
  if (s) return { text: "ESP32 offline", tone: "bad", detail: s.error ?? "Sem resposta da placa" };
  return { text: "verificando…", tone: "idle", detail: "Consultando o ESP32" };
}

/** Selo do topo. O texto (data-testid="esp-status") é o mesmo de antes. */
export function StatusPill({ view }: { view: DeviceView }) {
  const d = describeDevice(view);
  return (
    <span role="status" aria-live="polite" className={`status-pill ${d.tone}`}>
      {d.tone === "ok" ? <Wifi size={15} aria-hidden /> : <WifiOff size={15} aria-hidden />}
      <span data-testid="esp-status">{d.text}</span>
      {view.s?.info?.device?.includes("simulator") && <em className="sim-tag">simulador</em>}
    </span>
  );
}
