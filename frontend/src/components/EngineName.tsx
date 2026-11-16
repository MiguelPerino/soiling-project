import { Cpu, Server } from "lucide-react";
import type { Engine } from "../types";
import { ENGINE_NAME } from "../types";

export function EngineName({ engine }: { engine: Engine | undefined }) {
  const e = engine ?? "esp32";
  return (
    <span className="engine-name">
      {e === "esp32" ? <Cpu size={15} aria-hidden /> : <Server size={15} aria-hidden />}
      {ENGINE_NAME[e]}
    </span>
  );
}
