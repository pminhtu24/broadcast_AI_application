export type Intent = "qa" | "calculate" | "quote";

export interface CitationSource {
    filename: string;
    excerpt: string;
    score: number;
    search_type: string;
}

export interface QuoteFile {
    filename: string;
    url: string;
    price_list: string;
}

export interface ChatMessage {
    id: string;
    role: "user" | "assistant";
    content: string;
    intent?: Intent;
    citations?: CitationSource[];
    suggestions?: string[];
    quoteFiles?: QuoteFile[];
    isStreaming?: boolean;
    error?: boolean;
}

export interface Session {
    id: string;
    preview: string;
    createdAt: Date;
    messages?: ChatMessage[];
}

// SSE event types từ backend
export type SSEEvent =
    | { type: "meta"; intent: Intent; session_id: string }
    | { type: "token"; content: string }
    | { type: "citations"; data: CitationSource[] }
    | { type: "suggestions"; data: string[] }
    | { type: "quote"; files: QuoteFile[] }
    | { type: "done" }
    | { type: "error"; message: string };