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
        <div className="px-5 pb-5 pt-2">
            <div className={clsx(
                "flex items-end gap-3 bg-white border rounded-2xl px-4 py-3 transition-all duration-150",
                "border-border hover:border-border-strong focus-within:border-border-accent focus-within:shadow-input"
            )}>
                <textarea
                    ref={textareaRef}
                    onKeyDown={handleKey}
                    placeholder="Nhập câu hỏi về quảng cáo..."
                    disabled={isLoading}
                    rows={1}
                    className="flex-1 bg-transparent text-sm text-ink placeholder-ink-3 resize-none outline-none leading-relaxed min-h-[22px] disabled:opacity-60 font-serif"
                />
                <button
                    onClick={isLoading ? onStop : handleSend}
                    className={clsx(
                        "shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all duration-150",
                        isLoading
                            ? "bg-surface-2 hover:bg-surface-3 text-ink-2"
                            : "bg-teal hover:bg-teal-mid text-white shadow-sm"
                    )}
                >
                    {isLoading
                        ? <Square size={11} />
                        : <ArrowUp size={14} />
                    }
                </button>
            </div>
            <p className="text-center text-[10px] text-ink-3 mt-2">
                Enter để gửi · Shift+Enter xuống dòng
            </p>
        </div>
    );
}