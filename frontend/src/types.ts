export type Label = "LIMPO" | "MODERADO" | "SEVERO";
export const LABELS: Label[] = ["LIMPO", "MODERADO", "SEVERO"];

export interface Analysis {
  id: number;
  image_url: string;
  original_filename: string;
  classification: Label;
  final_label: Label;
  human_label: Label | null;
  confidence: number;
  probs: Record<string, number> | null;
  low_confidence: boolean;
  needs_review: boolean;
  cleaning_activated: boolean;
  pump_duration_ms: number;
  pump_reason: string | null;
  model_version: string | null;
  inference_ms: number | null;
  round_trip_ms: number | null;
  width: number;
  height: number;
  created_at: string;
  acao_sugerida: string;
}

export interface Config {
  input_size: number;
  jpeg_quality: number;
  max_upload_mb: number;
  low_confidence_threshold: number;
  ia_gemini: boolean;
  admin_protegido: boolean;
}

export interface DeviceStatus {
  configured: boolean;
  online: boolean;
  latency_ms?: number;
  error?: string;
  info?: { model_version?: string; device?: string; input_size?: number };
}

export interface Stats {
  total: number;
  por_rotulo: Record<Label, number>;
  para_revisao: number;
  revisadas: number;
  limpezas_acionadas: number;
  tempo_total_bomba_ms: number;
  confianca_media: number | null;
  inferencia_media_ms: number | null;
  ultima_analise: string | null;
  serie_diaria: ({ dia: string } & Record<Label, number>)[];
}

export interface AskResult {
  filtro_texto: string;
  total: number;
  analises: Analysis[];
  resumo: string;
  fonte: "gemini" | "regras";
}

export interface Filters {
  labels: Label[];
  needs_review: boolean;
  cleaning_activated: boolean;
}
