import { Plus, Trash2, MessageSquare } from "lucide-react";
import clsx from "clsx";
import type { Session } from "@/types";

interface Props {
    sessions: Session[];
    activeSessionId: string | null;
    onNewChat: () => void;
    onSwitch: (id: string) => void;
    onDelete: (id: string) => void;
}

export function Sidebar({
    sessions,
    activeSessionId,
    onNewChat,
    onSwitch,
    onDelete,
}: Props) {
    return (
        <aside className="flex flex-col w-56 shrink-0 border-r border-border bg-surface-1">
            {/* Logo */}
            <div className="px-4 pt-5 pb-4 border-b border-border">
                <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-md bg-accent flex items-center justify-center shrink-0">
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <path
                                d="M7 1L13 4V10L7 13L1 10V4L7 1Z"
                                stroke="white"
                                strokeWidth="1.2"
                                strokeLinejoin="round"
                            />
                            <circle cx="7" cy="7" r="2" fill="white" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-xs font-semibold text-white leading-tight">Broadcast AI</p>
                        <p className="text-[10px] text-white/40 leading-tight">Đài PT-TH Hải Phòng</p>
                    </div>
                </div>
            </div>

            {/* New chat */}
            <div className="px-3 pt-3">
                <button
                    onClick={onNewChat}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-white/60 hover:text-white hover:bg-surface-2 transition-colors border border-border hover:border-border-strong"
                >
                    <Plus size={13} />
                    Cuộc trò chuyện mới
                </button>
            </div>

            {/* Sessions */}
            <div className="flex-1 overflow-y-auto px-3 pt-3 pb-3 flex flex-col gap-1">
                {sessions.length === 0 && (
                    <p className="text-[11px] text-white/25 px-2 pt-2">
                        Chưa có lịch sử hội thoại
                    </p>
                )}
                {sessions.map((s) => (
                    <div
                        key={s.id}
                        className={clsx(
                            "group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors text-xs",
                            activeSessionId === s.id
                                ? "bg-surface-3 text-white"
                                : "text-white/50 hover:bg-surface-2 hover:text-white/80"
                        )}
                        onClick={() => onSwitch(s.id)}
                    >
                        <MessageSquare size={12} className="shrink-0 opacity-60" />
                        <span className="flex-1 truncate">{s.preview}</span>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onDelete(s.id);
                            }}
                            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity"
                        >
                            <Trash2 size={11} />
                        </button>
                    </div>
                ))}
            </div>
        </aside>
    );
}