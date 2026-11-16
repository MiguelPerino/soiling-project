import { Bot, Check, RefreshCw, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { dayLabel, hourLabel, pct } from "../lib/format";
import type { Analysis, Config } from "../types";
import { DetailModal } from "./DetailModal";
import { EngineName } from "./EngineName";
import { LabelBadge } from "./LabelBadge";

const EXAMPLES = ["fotos sujas de hoje", "análises que precisam de revisão", "quando a bomba foi acionada?", "painéis limpos da última semana"];
const INTRO = "Posso consultar as análises registradas ou tirar dúvidas gerais sobre sujeira em painéis solares. Escolha o modo e faça sua pergunta.";

interface Msg { role: "bot" | "user"; text: string; analises?: Analysis[]; foot?: string }

export function Assistant({ config, onChanged }: { config: Config; onChanged: () => void }) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"buscar" | "duvida">("buscar");
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "bot", text: INTRO }]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<Analysis | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView?.({ block: "end" }); }, [msgs, busy]);

  const go = async (text: string) => {
    if (text.trim().length < 2 || busy) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setQ(""); setBusy(true);
    try {
      if (mode === "buscar") {
        const r = await api.ask(text);
        setMsgs((m) => [...m, { role: "bot", text: r.resumo, analises: r.analises,
          foot: `Filtro aplicado: ${r.filtro_texto} · ${r.total} resultado(s) · resumo por ${r.fonte === "gemini" ? "Gemini" : "regras (sem IA)"}` }]);
      } else {
        const r = await api.explain(text);
        setMsgs((m) => [...m, { role: "bot", text: r.texto, foot: `${r.aviso} Fonte: ${r.fonte === "gemini" ? "Gemini" : "sem IA"}.` }]);
      }
    } catch (e) {
      setMsgs((m) => [...m, { role: "bot", text: e instanceof Error ? e.message : "Erro inesperado.", foot: "erro" }]);
    } finally { setBusy(false); }
  };

  return (
    <div className="page-content assistant-page">
      <div className="assistant-layout">
        <section className="chat-card card">
          <div className="chat-head">
            <div className="bot-avatar"><Bot size={21} aria-hidden /></div>
            <div><h2>Assistente de dados</h2><span><i /> {config.ia_gemini ? "IA: Gemini ativo" : "IA não configurada: usando regras simples"}</span></div>
            <button onClick={() => setMsgs([{ role: "bot", text: INTRO }])}><RefreshCw size={16} aria-hidden /> Nova conversa</button>
          </div>
          <div className="mode-switch" role="group" aria-label="Modo">
            <button className="chip" aria-pressed={mode === "buscar"} onClick={() => setMode("buscar")}>Buscar nas análises</button>
            <button className="chip" aria-pressed={mode === "duvida"} onClick={() => setMode("duvida")}>Tirar dúvida sobre soiling</button>
          </div>
          <div className="messages" aria-live="polite">
            {msgs.map((m, i) => (
              <div className={`message-row ${m.role}`} key={i}>
                {m.role === "bot" && <div className="bot-avatar small"><Bot size={17} aria-hidden /></div>}
                <div className="message">
                  <p className="pre-line" role={m.foot === "erro" ? "alert" : undefined}>{m.text}</p>
                  {m.analises && m.analises.length > 0 && (
                    <div className="answer-list">
                      {m.analises.map((a) => (
                        <button className="recent-row" key={a.id} data-testid="analysis-card" onClick={() => setOpen(a)}>
                          <img src={a.image_url} alt={`Foto ${a.id}`} loading="lazy" />
                          <div className="analysis-name"><strong>#{a.id}</strong><small>{dayLabel(a.created_at)}, {hourLabel(a.created_at)}</small></div>
                          <LabelBadge label={a.final_label} />
                          <EngineName engine={a.engine} />
                          <strong className="confidence">{pct(a.confidence)}</strong>
                        </button>
                      ))}
                    </div>
                  )}
                  {m.foot && m.foot !== "erro" && <small>{m.foot}</small>}
                </div>
              </div>
            ))}
            {busy && <div className="message-row bot"><div className="bot-avatar small"><Bot size={17} aria-hidden /></div><div className="typing" aria-label="Pensando"><i /><i /><i /></div></div>}
            <div ref={end} />
          </div>
          {mode === "buscar" && (
            <div className="suggestions"><span>Sugestões:</span>{EXAMPLES.map((x) => <button key={x} onClick={() => void go(x)}>{x}</button>)}</div>
          )}
          <form className="composer" onSubmit={(e) => { e.preventDefault(); void go(q); }}>
            <label htmlFor="q" className="sr-only">Pergunta</label>
            <input id="q" value={q} onChange={(e) => setQ(e.target.value)} maxLength={300}
              placeholder={mode === "buscar" ? "Ex.: fotos sujas de hoje" : "Ex.: por que a poeira reduz a geração?"} />
            <button type="submit" disabled={busy || q.trim().length < 2} aria-label="Perguntar"><Send size={18} aria-hidden /></button>
          </form>
          <p className="assistant-disclaimer"><ShieldCheck size={13} aria-hidden /> Na busca, o assistente responde só com os dados registrados. Nenhuma foto é enviada à IA.</p>
        </section>
        <aside className="assistant-side">
          <div className="card info-card">
            <Sparkles size={20} aria-hidden />
            <h3>Como posso ajudar?</h3>
            <p>Consulte contagens, períodos, mecanismos e análises que precisam de revisão, ou tire dúvidas sobre sujeira em painéis.</p>
            <div><Check size={14} aria-hidden /> Usa a classificação final</div>
            <div><Check size={14} aria-hidden /> Respeita correções humanas</div>
            <div><Check size={14} aria-hidden /> Não inventa resultados</div>
          </div>
        </aside>
      </div>
      {open && <DetailModal a={open} config={config} onClose={() => setOpen(null)} onChanged={onChanged} />}
    </div>
  );
}
