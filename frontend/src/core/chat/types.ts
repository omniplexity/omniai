export type ChatRole = "system" | "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error" | "stopped";
};

export type ChatRequest = {
  conversation_id?: string;
  input: string;

  // Optional; wired in Phase 4
  provider?: string;
  model?: string;
  settings?: {
    temperature?: number;
    top_p?: number;
    max_tokens?: number;
  };

  // Deterministic retry key (send identical payload)
  client_request_id: string;

  attachments?: Array<{ id: string; kind: string }>;
};

export type ChatStreamEvent =
  | { type: "delta"; text: string }
  | { type: "full"; content: string; message_id?: string; usage?: Record<string, number> }
  | { type: "error"; message: string }
  | { type: "done" }
  | { type: "stopped" }
  | { type: "meta"; conversation_id?: string; run_id?: string };
