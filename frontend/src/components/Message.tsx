import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import clsx from "clsx";
import type { ChatMessage } from "@/types";

interface Props {
    message: ChatMessage;
    onSuggestionClick?: (suggestion: string) => void;
}

export function Message({ message, onSuggestionClick }: Props) {
    const isUser = message.role === "user";

    if (isUser) {
        return (
            <div className="flex justify-end animate-slide-up">
                <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-accent text-white text-sm leading-relaxed">
                    {message.content}
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-2 animate-slide-up">
            {/* Intent badge */}
            {message.intent && (
                <div className="flex items-center gap-1.5">
                    <span
                        className={clsx(
                            "text-[10px] font-mono px-2 py-0.5 rounded-full border",
                            message.intent === "calculate"
                                ? "text-amber-400 border-amber-400/30 bg-amber-400/10"
                                : "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
                        )}
                    >
                        {message.intent === "calculate" ? "calculate" : "qa"}
                    </span>
                </div>
            )}

            {/* Bubble */}
            <div
                className={clsx(
                    "max-w-[85%] px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed",
                    message.error
                        ? "bg-red-500/10 border border-red-500/20 text-red-400"
                        : "bg-surface-2 text-white/85"
                )}
            >
                {message.content ? (
                    <>
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkMath]}
                            rehypePlugins={[rehypeKatex]}
                            components={{
                                p: ({ children }) => (
                                    <p className="mb-2 last:mb-0">{children}</p>
                                ),
                                ul: ({ children }) => (
                                    <ul className="list-disc list-inside mb-2 space-y-1">
                                        {children}
                                    </ul>
                                ),
                                ol: ({ children }) => (
                                    <ol className="list-decimal list-inside mb-2 space-y-1">
                                        {children}
                                    </ol>
                                ),
                                strong: ({ children }) => (
                                    <strong className="font-semibold text-white">
                                        {children}
                                    </strong>
                                ),
                                code: ({ children }) => (
                                    <code className="font-mono text-xs bg-surface-3 px-1.5 py-0.5 rounded text-accent">
                                        {children}
                                    </code>
                                ),
                                table: ({ children }) => (
                                    <div className="overflow-x-auto my-2">
                                        <table className="text-xs border-collapse w-full">
                                            {children}
                                        </table>
                                    </div>
                                ),
                                th: ({ children }) => (
                                    <th className="border border-border px-3 py-1.5 text-left text-white/60 font-medium bg-surface-3">
                                        {children}
                                    </th>
                                ),
                                td: ({ children }) => (
                                    <td className="border border-border px-3 py-1.5">{children}</td>
                                ),
                            }}
                        >
                            {message.content}
                        </ReactMarkdown>
                        {/* Streaming cursor */}
                        {message.isStreaming && (
                            <span className="inline-block w-0.5 h-4 bg-white/60 ml-0.5 align-text-bottom animate-blink" />
                        )}
                    </>
                ) : (
                    // Typing indicator khi chưa có token nào
                    <div className="flex items-center gap-1.5 py-0.5">
                        {[0, 1, 2].map((i) => (
                            <span
                                key={i}
                                className="w-1.5 h-1.5 rounded-full bg-white/30 animate-bounce"
                                style={{ animationDelay: `${i * 0.15}s` }}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Citations */}
            {message.citations && message.citations.length > 0 && (
                <div className="flex flex-col gap-1 max-w-[85%]">
                    {message.citations.map((c, i) => (
                        <div
                            key={i}
                            className="flex items-start gap-2 px-3 py-2 rounded-lg bg-surface-1 border border-border text-[11px]"
                        >
                            <div className="w-1 h-1 rounded-full bg-accent mt-1.5 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <span className="text-white/50 font-mono truncate block">
                                    {c.filename}
                                </span>
                                <span className="text-white/25">
                                    score {c.score.toFixed(2)} · {c.search_type}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Suggestions */}
            {message.suggestions && message.suggestions.length > 0 && (
                <div className="flex flex-col gap-1.5 max-w-[85%]">
                    <span className="text-[11px] text-white/40 font-medium">
                        Câu hỏi gợi ý
                    </span>
                    <div className="flex flex-wrap gap-2">
                        {message.suggestions.map((s, i) => (
                            <button
                                key={i}
                                className="px-3 py-1.5 rounded-full bg-surface-1 border border-border text-xs text-white/70 hover:text-white hover:border-accent/50 transition-colors cursor-pointer"
                                onClick={() => onSuggestionClick?.(s)}
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}