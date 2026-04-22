import { useState, useCallback, useRef, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import { streamChat, deleteSession, getSessions, getSessionHistory } from "@/lib/api";
import type { ChatMessage, Session, CitationSource, Intent } from "@/types";

export function useChat() {
    const [sessions, setSessions] = useState<Session[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [updateTrigger, setUpdateTrigger] = useState(0);
    const abortRef = useRef<AbortController | null>(null);

    const messagesMapRef = useRef<Map<string, ChatMessage[]>>(new Map());

    const getCurrentMessages = useCallback((): ChatMessage[] => {
        if (!sessionId) return [];
        return messagesMapRef.current.get(sessionId) ?? [];
    }, [sessionId, updateTrigger]);

    useEffect(() => {
        getSessions().then((loadedSessions) => {
            setSessions(loadedSessions);
            loadedSessions.forEach((s) => {
                if (s.messages) {
                    messagesMapRef.current.set(s.id, s.messages);
                }
            });
        }).catch((err) => {
            console.error("Failed to load sessions:", err);
        });
    }, []);

    const sendMessage = useCallback(
        (text: string) => {
            if (!text.trim() || isLoading) return;

            const userMsg: ChatMessage = {
                id: uuidv4(),
                role: "user",
                content: text,
            };

            const assistantId = uuidv4();
            const assistantMsg: ChatMessage = {
                id: assistantId,
                role: "assistant",
                content: "",
                isStreaming: true,
            };

            let currentSessionId = sessionId;

            if (!currentSessionId) {
                currentSessionId = uuidv4();
                setSessionId(currentSessionId);
                messagesMapRef.current.set(currentSessionId, []);
                setSessions((prev) => [
                    {
                        id: currentSessionId,
                        preview: text.slice(0, 50),
                        createdAt: new Date(),
                    } as Session,
                    ...prev,
                ]);
            }

            const newMessages = [...(messagesMapRef.current.get(currentSessionId) ?? []), userMsg, assistantMsg];
            messagesMapRef.current.set(currentSessionId, newMessages);

            setIsLoading(true);

            let resolvedIntent: Intent = "qa";

            abortRef.current = streamChat(text, currentSessionId, {
                onMeta: (intent, newSessionId) => {
                    resolvedIntent = intent as Intent;

                    if (newSessionId !== currentSessionId && newSessionId) {
                        currentSessionId = newSessionId;
                        setSessionId(newSessionId);
                        messagesMapRef.current.set(newSessionId, messagesMapRef.current.get(sessionId!) ?? []);
                        setSessions((prev) => {
                            if (prev.some((s) => s.id === newSessionId)) return prev;
                            return [
                                {
                                    id: newSessionId,
                                    preview: text.slice(0, 50),
                                    createdAt: new Date(),
                                },
                                ...prev,
                            ];
                        });
                    }
                },

                onToken: (token) => {
                    messagesMapRef.current.set(
                        currentSessionId!,
                        (messagesMapRef.current.get(currentSessionId!) ?? []).map((m) =>
                            m.id === assistantId ? { ...m, content: m.content + token } : m
                        )
                    );
                    setUpdateTrigger((v) => v + 1);
                },

                onCitations: (citations: CitationSource[]) => {
                    messagesMapRef.current.set(
                        currentSessionId!,
                        (messagesMapRef.current.get(currentSessionId!) ?? []).map((m) =>
                            m.id === assistantId ? { ...m, citations } : m
                        )
                    );
                    setUpdateTrigger((v) => v + 1);
                },

                onSuggestions: (suggestions: string[]) => {
                    messagesMapRef.current.set(
                        currentSessionId!,
                        (messagesMapRef.current.get(currentSessionId!) ?? []).map((m) =>
                            m.id === assistantId ? { ...m, suggestions } : m
                        )
                    );
                    setUpdateTrigger((v) => v + 1);
                },

                onDone: () => {
                    messagesMapRef.current.set(
                        currentSessionId!,
                        (messagesMapRef.current.get(currentSessionId!) ?? []).map((m) =>
                            m.id === assistantId
                                ? { ...m, isStreaming: false, intent: resolvedIntent }
                                : m
                        )
                    );
                    setIsLoading(false);
                    setUpdateTrigger((v) => v + 1);
                },

                onError: (message) => {
                    messagesMapRef.current.set(
                        currentSessionId!,
                        (messagesMapRef.current.get(currentSessionId!) ?? []).map((m) =>
                            m.id === assistantId
                                ? { ...m, content: `Đã có lỗi xảy ra: ${message}`, isStreaming: false, error: true }
                                : m
                        )
                    );
                    setIsLoading(false);
                    setUpdateTrigger((v) => v + 1);
                },
            });
        },
        [isLoading, sessionId, updateTrigger]
    );

    const newChat = useCallback(() => {
        abortRef.current?.abort();
        setSessionId(null);
        setIsLoading(false);
    }, []);

    const clearSession = useCallback(
        async (id: string) => {
            await deleteSession(id);
            setSessions((prev) => prev.filter((s) => s.id !== id));
            messagesMapRef.current.delete(id);
            if (sessionId === id) {
                setSessionId(null);
            }
        },
        [sessionId]
    );

    const switchSession = useCallback(
        async (id: string) => {
            if (sessionId === id) return;
            abortRef.current?.abort();
            setSessionId(id);
            setIsLoading(false);

            if (!messagesMapRef.current.has(id)) {
                try {
                    const history = await getSessionHistory(id);
                    messagesMapRef.current.set(id, history);
                } catch (err) {
                    console.error("Failed to load session history:", err);
                    messagesMapRef.current.set(id, []);
                }
            }
        },
        [sessionId]
    );

    return {
        sessions,
        sessionId,
        isLoading,
        getCurrentMessages,
        sendMessage,
        newChat,
        clearSession,
        switchSession,
    };
}