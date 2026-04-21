import type { SSEEvent, CitationSource } from "@/types";

const BASE = "/api";

export interface StreamCallbacks {
    onMeta: (intent: string, sessionId: string) => void;
    onToken: (token: string) => void;
    onCitations: (citations: CitationSource[]) => void;
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