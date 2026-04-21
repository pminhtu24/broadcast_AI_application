import { useState, useCallback, useRef } from "react";
import { v4 as uuidv4 } from "uuid";
import { streamChat, deleteSession } from "@/lib/api";
import type { ChatMessage, Session, CitationSource, Intent } from "@/types";

export function useChat() {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [sessions, setSessions] = useState<Session[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const abortRef = useRef<AbortController | null>(null);

    const sendMessage = useCallback(
        (text: string) => {
            if (!text.trim() || isLoading) return;

            // Thêm user message
            const userMsg: ChatMessage = {
                id: uuidv4(),
                role: "user",
                content: text,
            };

            // Placeholder assistant message đang streaming
            const assistantId = uuidv4();
            const assistantMsg: ChatMessage = {
                id: assistantId,
                role: "assistant",
                content: "",
                isStreaming: true,
            };

            setMessages((prev) => [...prev, userMsg, assistantMsg]);
            setIsLoading(true);

            let currentSessionId = sessionId;
            let resolvedIntent: Intent = "qa";

            abortRef.current = streamChat(text, currentSessionId, {
                onMeta: (intent, newSessionId) => {
                    resolvedIntent = intent as Intent;

                    // Lần đầu tiên → tạo session mới
                    if (!currentSessionId) {
                        currentSessionId = newSessionId;
                        setSessionId(newSessionId);
                        setSessions((prev) => [
                            {
                                id: newSessionId,
                                preview: text.slice(0, 50),
                                createdAt: new Date(),
                            },
                            ...prev,
                        ]);
                    }
                },

                onToken: (token) => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === assistantId
                                ? { ...m, content: m.content + token }
                                : m
                        )
                    );
                },

                onCitations: (citations: CitationSource[]) => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === assistantId ? { ...m, citations } : m
                        )
                    );
                },

                onDone: () => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === assistantId
                                ? { ...m, isStreaming: false, intent: resolvedIntent }
                                : m
                        )
                    );
                    setIsLoading(false);
                },

                onError: (message) => {
                    setMessages((prev) =>
                        prev.map((m) =>
                            m.id === assistantId
                                ? {
                                    ...m,
                                    content: `Đã có lỗi xảy ra: ${message}`,
                                    isStreaming: false,
                                    error: true,
                                }
                                : m
                        )
                    );
                    setIsLoading(false);
                },
            });
        },
        [isLoading, sessionId]
    );

    const newChat = useCallback(() => {
        // Cancel stream đang chạy nếu có
        abortRef.current?.abort();
        setMessages([]);
        setSessionId(null);
        setIsLoading(false);
    }, []);

    const clearSession = useCallback(
        async (id: string) => {
            await deleteSession(id);
            setSessions((prev) => prev.filter((s) => s.id !== id));
            if (sessionId === id) newChat();
        },
        [sessionId, newChat]
    );

    const switchSession = useCallback((id: string) => {
        // Chỉ switch session_id, messages sẽ load từ server khi send message đầu tiên
        setSessionId(id);
        setMessages([]);
    }, []);

    return {
        messages,
        sessions,
        sessionId,
        isLoading,
        sendMessage,
        newChat,
        clearSession,
        switchSession,
    };
}