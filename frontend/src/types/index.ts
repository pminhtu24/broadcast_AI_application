export type Intent = "qa" | "calculate";

export interface CitationSource {
    filename: string;
    excerpt: string;
    score: number;
    search_type: string;
}

export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    intent?: Intent;
    citations?: CitationSource[];
    isStreaming?: boolean;
    error?: boolean;
}

export interface Session {
    id: string;
    preview: string; // first message preview
    createdAt: Date;
}

// SSE event types từ backend
export type SSEEvent =
    | { type: "meta"; intent: Intent; session_id: string }
    | { type: "token"; content: string }
    | { type: "citations"; data: CitationSource[] }
    | { type: "done" }
    | { type: "error"; message: string };