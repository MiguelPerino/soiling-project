import { FileImage } from "lucide-react";
import type { ElementType } from "react";

export function EmptyState({ icon: Icon = FileImage, title, text }: { icon?: ElementType; title: string; text: string }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Icon size={23} aria-hidden /></div>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
