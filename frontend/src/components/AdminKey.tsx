import { Check, KeyRound, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { getAdminKey, setAdminKey } from "../api";

/** Janelinha da chave de administrador. A chave fica só nesta aba (sessionStorage) e é enviada no cabeçalho X-API-Key. */
export function AdminPopover({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [v, setV] = useState(getAdminKey());
  return (
    <div className="admin-popover" role="dialog" aria-label="Chave de administrador">
      <div>
        <KeyRound size={18} aria-hidden />
        <span>
          <strong>Chave de administrador</strong>
          <small>Necessária para acionar a bomba, corrigir rótulos e apagar</small>
        </span>
        <button onClick={onClose} aria-label="Fechar"><X size={16} /></button>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); setAdminKey(v.trim()); onSaved(); onClose(); }}>
        <label htmlFor="adminkey">CHAVE DA SESSÃO</label>
        <div className="key-field">
          <input id="adminkey" type="password" value={v} onChange={(e) => setV(e.target.value)} autoComplete="off" />
          <ShieldCheck size={16} aria-hidden />
        </div>
        <button type="submit" className="primary-button admin-save"><Check size={16} aria-hidden /> Salvar</button>
      </form>
      <small>A chave permanece somente nesta aba do navegador. Ela só é conferida quando você usa uma ação protegida.</small>
    </div>
  );
}
