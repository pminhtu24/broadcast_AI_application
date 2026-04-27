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

export function Sidebar({ sessions, activeSessionId, onNewChat, onSwitch, onDelete }: Props) {
    return (
        <aside className="flex flex-col w-60 shrink-0 bg-teal shadow-sidebar">
            {/* Logo */}
            <div className="px-5 pt-5 pb-4 border-b border-white/10">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center shrink-0">
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                            <path d="M8 1.5L14 4.5V11.5L8 14.5L2 11.5V4.5L8 1.5Z"
                                stroke="white" strokeWidth="1.2" strokeLinejoin="round" />
                            <circle cx="8" cy="8" r="2.2" fill="white" />
                        </svg>
                    </div>
                    <div>
                        <p className="text-sm font-semibold text-white font-serif leading-tight">
                            Broadcast AI
                        </p>
                        <p className="text-[10px] text-white/60 leading-tight mt-0.5">
                            Đài PT-TH Hải Phòng
                        </p>
                    </div>
                </div>
            </div>

            {/* New chat button */}
            <div className="px-3 pt-3">
                <button
                    onClick={onNewChat}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-white hover:bg-white/10 border border-white/30 hover:border-white/50 transition-all duration-150"
                >
                    <Plus size={13} className="shrink-0" />
                    Cuộc trò chuyện mới
                </button>
            </div>

            {/* Sessions */}
            <div className="flex-1 overflow-y-auto px-3 pt-2 pb-3 flex flex-col gap-0.5">
                {sessions.length === 0 && (
                    <p className="text-[11px] text-white/40 px-2 pt-3">
                        Chưa có lịch sử hội thoại
                    </p>
                )}
                {sessions.map((s) => (
                    <div
                        key={s.id}
                        className={clsx(
                            "group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all duration-150 text-xs",
                            activeSessionId === s.id
                                ? "bg-white/15 text-white font-medium"
                                : "text-white/70 hover:bg-white/10 hover:text-white"
                        )}
                        onClick={() => onSwitch(s.id)}
                    >
                        <MessageSquare
                            size={12}
                            className={clsx(
                                "shrink-0",
                                activeSessionId === s.id ? "text-teal-light" : "opacity-60"
                            )}
                        />
                        <span className="flex-1 truncate">{s.preview}</span>
                        <button
                            onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                            className="opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity text-white/60 hover:text-red-400"
                        >
                            <Trash2 size={11} />
                        </button>
                    </div>
                ))}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-white/10">
                <p className="text-[10px] text-white/40">
                    Broadcast AI · Đài PT-TH Hải Phòng
                </p>
            </div>
        </aside>
    );
}