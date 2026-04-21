import { useEffect, useRef } from "react";
import { Sidebar } from "@/components/Sidebar";
import { Message } from "@/components/Message";
import { ChatInput } from "@/components/ChatInput";
import { useChat } from "@/hooks/useChat";

export function ChatPage() {
    const {
        messages,
        sessions,
        sessionId,
        isLoading,
        sendMessage,
        newChat,
        clearSession,
        switchSession,
    } = useChat();

    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto scroll xuống khi có message mới hoặc token mới
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const isEmpty = messages.length === 0;

    return (
        <div className="flex h-screen bg-surface text-white font-sans overflow-hidden">
            <Sidebar
                sessions={sessions}
                activeSessionId={sessionId}
                onNewChat={newChat}
                onSwitch={switchSession}
                onDelete={clearSession}
            />

            {/* Main */}
            <div className="flex flex-col flex-1 min-w-0">
                {/* Topbar */}
                <header className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
                    <div>
                        <h1 className="text-sm font-semibold text-white">
                            Trợ lý Quảng cáo
                        </h1>
                        <p className="text-xs text-white/35">
                            Hỏi về giá, dịch vụ, hoặc yêu cầu tính toán chi phí
                        </p>
                    </div>
                    {sessionId && (
                        <span className="text-[10px] font-mono text-white/25">
                            {sessionId.slice(0, 8)}
                        </span>
                    )}
                </header>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-5 py-6 flex flex-col gap-5">
                    {isEmpty ? (
                        <EmptyState onSuggestion={sendMessage} />
                    ) : (
                        messages.map((m) => <Message key={m.id} message={m} />)
                    )}
                    <div ref={bottomRef} />
                </div>

                <ChatInput
                    onSend={sendMessage}
                    isLoading={isLoading}
                />
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Empty state với suggested questions
// ---------------------------------------------------------------------------

const SUGGESTIONS = [
    "Giá quảng cáo khung giờ vàng trên HPTV1 là bao nhiêu?",
    "Tính chi phí chạy 30 giây x 10 lần trong tháng",
    "Các gói quảng cáo theo tháng có những loại nào?",
    "Điều kiện để được chiết khấu 15%?",
];

function EmptyState({ onSuggestion }: { onSuggestion: (s: string) => void }) {
    return (
        <div className="flex flex-col items-center justify-center flex-1 gap-8 py-16 animate-fade-in">
            <div className="text-center">
                <div className="w-12 h-12 rounded-2xl bg-accent/15 border border-accent/20 flex items-center justify-center mx-auto mb-4">
                    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                        <path
                            d="M11 2L20 6.5V15.5L11 20L2 15.5V6.5L11 2Z"
                            stroke="#3b82f6"
                            strokeWidth="1.5"
                            strokeLinejoin="round"
                        />
                        <circle cx="11" cy="11" r="3" fill="#3b82f6" />
                    </svg>
                </div>
                <h2 className="text-lg font-semibold text-white mb-1">
                    Xin chào! Tôi có thể giúp gì cho bạn?
                </h2>
                <p className="text-sm text-white/40">
                    Hỏi về bảng giá, dịch vụ, hoặc yêu cầu tính toán chi phí quảng cáo
                </p>
            </div>

            <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
                {SUGGESTIONS.map((s) => (
                    <button
                        key={s}
                        onClick={() => onSuggestion(s)}
                        className="text-left px-4 py-3 rounded-xl bg-surface-2 border border-border hover:border-accent/30 hover:bg-surface-3 text-xs text-white/60 hover:text-white/90 transition-all leading-relaxed"
                    >
                        {s}
                    </button>
                ))}
            </div>
        </div>
    );
}