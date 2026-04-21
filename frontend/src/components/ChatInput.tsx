import { useRef, useEffect, KeyboardEvent } from "react";
import { ArrowUp, Square } from "lucide-react";
import clsx from "clsx";

interface Props {
    onSend: (text: string) => void;
    isLoading: boolean;
    onStop?: () => void;
}

export function ChatInput({ onSend, isLoading, onStop }: Props) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
    useEffect(() => {
        const el = textareaRef.current;
        if (!el) return;
        el.style.height = "auto";
        el.style.height = Math.min(el.scrollHeight, 160) + "px";
    });

    const handleSend = () => {
        const val = textareaRef.current?.value.trim();
        if (!val || isLoading) return;
        onSend(val);
        if (textareaRef.current) {
            textareaRef.current.value = "";
            textareaRef.current.style.height = "auto";
        }
    };

    const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="px-4 pb-4 pt-2">
            <div className="flex items-end gap-2 bg-surface-2 border border-border hover:border-border-strong focus-within:border-accent/50 rounded-2xl px-4 py-3 transition-colors">
                <textarea
                    ref={textareaRef}
                    onKeyDown={handleKey}
                    placeholder="Nhập câu hỏi về quảng cáo..."
                    disabled={isLoading}
                    rows={1}
                    className="flex-1 bg-transparent text-sm text-white placeholder-white/25 resize-none outline-none leading-relaxed min-h-[22px] disabled:opacity-50"
                />
                <button
                    onClick={isLoading ? onStop : handleSend}
                    className={clsx(
                        "shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all",
                        isLoading
                            ? "bg-white/10 hover:bg-white/15 text-white/60"
                            : "bg-accent hover:bg-accent-hover text-white"
                    )}
                >
                    {isLoading ? <Square size={12} /> : <ArrowUp size={14} />}
                </button>
            </div>
            <p className="text-center text-[10px] text-white/20 mt-2">
                Enter để gửi · Shift+Enter xuống dòng
            </p>
        </div>
    );
}