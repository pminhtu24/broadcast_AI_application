import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import clsx from "clsx";
import { Download } from "lucide-react";
import type { ChatMessage } from "@/types";
import { downloadQuote } from "@/lib/api";

function normalizeMathContent(content: string): string {
    return content
        .normalize("NFC")
        // Normalize Unicode spaces frequently returned by LLM output
        .replace(/[\u00A0\u2000-\u200B\u202F\u205F\u3000]/g, " ")
        // Clean latex text wrappers in normal/table text
        .replace(/\\+text\s*\{([^{}]*)\}/g, "$1")
        // Unwrap inline latex delimiters: \( ... \) -> ...
        .replace(/\\\(\s*([\s\S]*?)\s*\\\)/g, "$1")
        // Convert latex thousand grouping: 28{,}000{,}000 -> 28.000.000
        .replace(/(\d)\s*\{,\}\s*(\d)/g, "$1.$2")
        // Remove redundant parentheses around plain formatted numbers: (500.000) -> 500.000
        .replace(/\(\s*(\d{1,3}(?:\.\d{3})+)\s*\)/g, "$1")
        // Convert escaped display delimiters: \[ ... \] -> $$ ... $$
        .replace(/\\\[\s*([\s\S]*?)\s*\\\]/g, (_, expr: string) => `$$${expr}$$`)
        // Convert display math in bracket form: [ ... ] -> $$ ... $$ (single or multi-line block)
        .replace(/(^|\n)\s*\[\s*([\s\S]*?)\s*\]\s*(?=\n|$)/g, (_, prefix: string, expr: string) => {
            const normalizedExpr = expr
                // In aligned blocks, model often emits "\[4pt]" instead of "\\[4pt]"
                .replace(/\\\[(\d+pt)\]/g, "\\\\[$1]");
            return `${prefix}$$${normalizedExpr}$$`;
        })
        // Fix common LLM typo in formulas: ";=;" / ";-;" -> "=" / "-"
        .replace(/;\s*=\s*;/g, "=")
        .replace(/;\s*-\s*;/g, "-")
        // KaTeX/remark-math handles line breaks inside aligned with \\
        .replace(/\\\s+(?=\\text)/g, "\\\\ ")
        .replace(/\\\s+\n/g, "\\\\\n")
        .trim();
}

interface Props {
    message: ChatMessage;
    onSuggestionClick?: (suggestion: string) => void;
}

export function Message({ message, onSuggestionClick }: Props) {
    const isUser = message.role === "user";
    const normalizedContent = message.content
        ? normalizeMathContent(message.content)
        : "";

    if (isUser) {
        return (
            <div className="flex justify-end animate-slide-up">
                <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-br-sm bg-teal text-white text-sm leading-relaxed">
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
                                : message.intent === "quote"
                                ? "text-blue-400 border-blue-400/30 bg-blue-400/10"
                                : "text-emerald-400 border-emerald-400/30 bg-emerald-400/10"
                        )}
                    >
                        {message.intent}
                    </span>
                </div>
            )}

            {/* Bubble */}
            <div
                className={clsx(
                    "max-w-[85%] px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed",
                    message.error
                        ? "bg-red-500/10 border border-red-500/20 text-red-400"
                        : "bg-surface-2 text-ink"
                )}
            >
                {message.content ? (
                    <>
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm, remarkMath]}
                            rehypePlugins={[
                                [
                                    rehypeKatex,
                                    {
                                        throwOnError: false,
                                        strict: "ignore",
                                    },
                                ],
                            ]}
                            components={{
                                p: ({ children }) => (
                                    <p className="mb-2 last:mb-0 text-ink">{children}</p>
                                ),
                                ul: ({ children }) => (
                                    <ul className="list-disc list-inside mb-2 space-y-1 text-ink">
                                        {children}
                                    </ul>
                                ),
                                ol: ({ children }) => (
                                    <ol className="list-decimal list-inside mb-2 space-y-1 text-ink">
                                        {children}
                                    </ol>
                                ),
                                strong: ({ children }) => (
                                    <strong className="font-semibold text-ink">
                                        {children}</strong>
                                ),
                                code: ({ children, className, ...props }) => {
                                    const code = String(children);
                                    const isInline = !(props as any).nodeName || (props as any).nodeName === '#text';
                                    if (isInline) {
                                        return <code className="font-mono text-xs bg-surface-3 px-1.5 py-0.5 rounded text-ink">{code}</code>;
                                    }
                                    return <code className={className}>{children}</code>;
                                },
                                table: ({ children }) => (
                                    <div className="overflow-x-auto my-2">
                                        <table className="text-xs border-collapse w-full">
                                            {children}
                                        </table>
                                    </div>
                                ),
                                th: ({ children }) => (
                                    <th className="border border-border px-3 py-1.5 text-left text-ink font-bold bg-surface-3">
                                        {children}
                                    </th>
                                ),
                                td: ({ children }) => (
                                    <td className="border border-border px-3 py-1.5 text-ink">{children}</td>
                                ),
                                pre: ({ children }) => (
                                    <pre className="bg-transparent p-0 m-0 font-sans text-sm text-ink overflow-visible">
                                        <code>{children}</code>
                                    </pre>
                                ),
                            }}
                        >
                            {normalizedContent}
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
                            <div className="w-1 h-1 rounded-full bg-teal-light mt-1.5 shrink-0" />
                            <div className="flex-1 min-w-0">
                                <span className="text-ink-2 font-mono truncate block">
                                    {c.filename}
                                </span>
                                <span className="text-ink-3">
                                    score {c.score.toFixed(2)} · {c.search_type}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Quote Files Download */}
            {message.quoteFiles && message.quoteFiles.length > 0 && (
                <div className="flex flex-col gap-2 max-w-[85%] mt-2">
                    <span className="text-[11px] text-ink-2 font-medium">
                        File báo giá
                    </span>
                    <div className="flex flex-wrap gap-2">
                        {message.quoteFiles.map((file, i) => (
                            <button
                                key={i}
                                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-1 border border-teal-light/30 text-xs text-ink hover:text-teal hover:border-teal-light transition-colors cursor-pointer"
                                onClick={() => downloadQuote(file.url, file.filename)}
                            >
                                <Download className="w-4 h-4 text-teal-light" />
                                <span>{file.price_list}</span>
                                <span className="text-ink-3">DOCX</span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Suggestions */}
            {message.suggestions && message.suggestions.length > 0 && (
                <div className="flex flex-col gap-1.5 max-w-[85%]">
                    <span className="text-[11px] text-ink-2 font-medium">
                        Câu hỏi gợi ý
                    </span>
                    <div className="flex flex-wrap gap-2">
                        {message.suggestions.map((s, i) => (
                            <button
                                key={i}
                                className="px-3 py-1.5 rounded-full bg-surface-1 border border-border text-xs text-ink-2 hover:text-ink hover:border-teal-light/50 transition-colors cursor-pointer"
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