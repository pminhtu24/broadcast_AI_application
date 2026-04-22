import type { SSEEvent, CitationSource, ChatMessage, Session } from "@/types";

const BASE = "/api";

export interface StreamCallbacks {
    onMeta: (intent: string, sessionId: string) => void;
    onToken: (token: string) => void;
    onCitations: (citations: CitationSource[]) => void;
    onSuggestions: (suggestions: string[]) => void;
    onDone: () => void;
    onError: (message: string) => void;
}

/**
 * Gọi POST /api/chat/stream và parse SSE events.
 * Trả về AbortController để caller có thể cancel stream.
 */
export function streamChat(
    message: string,
    sessionId: string | null,
    callbacks: StreamCallbacks
): AbortController {
    const controller = new AbortController();

    (async () => {
        try {
            const res = await fetch(`${BASE}/chat/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    session_id: sessionId ?? undefined,
                }),
                signal: controller.signal,
            });

            if (!res.ok) {
                callbacks.onError(`Server error: ${res.status}`);
                return;
            }

            const reader = res.body?.getReader();
            if (!reader) {
                callbacks.onError("No response body");
                return;
            }

            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Parse SSE — mỗi event kết thúc bằng "\n\n"
                const parts = buffer.split("\n\n");
                buffer = parts.pop() ?? "";

                for (const part of parts) {
                    const line = part.trim();
                    if (!line.startsWith("data:")) continue;

                    const json = line.slice("data:".length).trim();
                    try {
                        const event: SSEEvent = JSON.parse(json);
                        switch (event.type) {
                            case "meta":
                                callbacks.onMeta(event.intent, event.session_id);
                                break;
                            case "token":
                                callbacks.onToken(event.content);
                                break;
                            case "citations":
                                callbacks.onCitations(event.data);
                                break;
                            case "suggestions":
                                callbacks.onSuggestions(event.data);
                                break;
                            case "done":
                                callbacks.onDone();
                                break;
                            case "error":
                                callbacks.onError(event.message);
                                break;
                        }
                    } catch {
                        // bỏ qua malformed event
                    }
                }
            }
        } catch (err) {
            if ((err as Error).name !== "AbortError") {
                callbacks.onError((err as Error).message ?? "Unknown error");
            }
        }
    })();

    return controller;
}

/**
 * Xoá session history khỏi Neo4j.
 */
export async function deleteSession(sessionId: string): Promise<void> {
    await fetch(`${BASE}/chat/${sessionId}`, { method: "DELETE" });
}

interface SessionResponse {
    id: string;
    updatedAt: string;
    createdAt: string;
}

interface HistoryResponse {
    messages: Array<{ role: string; content: string }>;
}

/**
 * Lấy danh sách tất cả sessions từ Neo4j.
 */
export async function getSessions(): Promise<Session[]> {
    const res = await fetch(`${BASE}/chat/sessions`);
    if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.status}`);
    const data: { sessions: SessionResponse[] } = await res.json();

    const sessionsWithMessages: Session[] = [];
    for (const s of data.sessions) {
        try {
            const historyRes = await fetch(`${BASE}/chat/${s.id}/history`);
            if (!historyRes.ok) continue;
            const historyData: HistoryResponse = await historyRes.json();
            const firstUserMessage = historyData.messages.find((m) => m.role === "user");
            sessionsWithMessages.push({
                id: s.id,
                preview: firstUserMessage?.content.slice(0, 50) ?? "Cuộc trò chuyện",
                createdAt: s.createdAt ? new Date(s.createdAt) : new Date(),
                messages: historyData.messages.map((m, i) => ({
                    id: `${s.id}-${i}`,
                    role: m.role as "user" | "assistant",
                    content: m.content,
                })) as ChatMessage[],
            });
        } catch {
            continue;
        }
    }

    return sessionsWithMessages;
}

/**
 * Lấy message history của một session.
 */
export async function getSessionHistory(sessionId: string): Promise<ChatMessage[]> {
    const res = await fetch(`${BASE}/chat/${sessionId}/history`);
    if (!res.ok) throw new Error(`Failed to fetch history: ${res.status}`);
    const data: HistoryResponse = await res.json();
    return data.messages.map((m, i) => ({
        id: `${sessionId}-${i}`,
        role: m.role as "user" | "assistant",
        content: m.content,
    }));
}