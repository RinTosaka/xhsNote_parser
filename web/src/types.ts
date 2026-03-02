export type ParseOptions = {
  timeout?: number | null;
  user_agent?: string;
  cookie?: string;
  save?: boolean;
  save_initial_state?: boolean;
};

export type ParseRequest = {
  url: string;
  options?: ParseOptions;
};

export type SavedPaths = {
  note_detail?: string | null;
  initial_state?: string | null;
};

export type ParseResponse = {
  url: string;
  note: Record<string, any>;
  saved?: SavedPaths | null;
  initial_state?: Record<string, any> | null;
  elapsed_ms: number;
};

export type BatchParseRequest = {
  urls: string[];
  options?: ParseOptions;
  concurrency?: number;
  dedupe?: boolean;
};

export type BatchItem = {
  url: string;
  ok: boolean;
  result?: ParseResponse;
  error?: string;
};

export type BatchResponse = {
  items: BatchItem[];
  total: number;
  ok: number;
  failed: number;
  elapsed_ms: number;
};

export type OutputItem = {
  relative_path: string;
  absolute_path: string;
  size: number;
  modified_time: string;
  kind: string;
};

export type OutputListResponse = {
  items: OutputItem[];
  total: number;
};
