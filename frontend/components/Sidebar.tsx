"use client";

import type { UserInfo } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { FC } from "react";

interface ConversationItem {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
}

interface SidebarProps {
  conversations: ConversationItem[];
  activeConvId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  user: UserInfo;
  onLogout: () => void;
}

export const Sidebar: FC<SidebarProps> = ({
  conversations,
  activeConvId,
  onSelect,
  onNew,
  onDelete,
  onClose,
  user,
  onLogout,
}) => {
  return (
    <aside className="flex w-64 flex-col border-r bg-muted/30">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between border-b px-3 py-2.5">
        <button
          onClick={onNew}
          className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
        >
          <svg
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4.5v15m7.5-7.5h-15"
            />
          </svg>
          新对话
        </button>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
          title="收起侧栏"
        >
          <svg
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M18.75 19.5l-7.5-7.5 7.5-7.5m-6 15L5.25 12l7.5-7.5"
            />
          </svg>
        </button>
      </div>

      {/* 对话列表 */}
      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {conversations.length === 0 ? (
          <p className="px-2 py-4 text-center text-xs text-muted-foreground">
            暂无对话，点击上方创建
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((conv) => (
              <li key={conv.id} className="group relative">
                <button
                  onClick={() => onSelect(conv.id)}
                  className={cn(
                    "flex w-full items-center rounded-lg px-3 py-2 text-left text-sm transition-colors",
                    activeConvId === conv.id
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-foreground hover:bg-muted",
                  )}
                >
                  <span className="truncate">{conv.title}</span>
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(conv.id);
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  title="删除对话"
                >
                  <svg
                    className="size-3.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0"
                    />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>

      {/* 底部用户信息 */}
      <div className="border-t px-3 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <span className="max-w-[120px] truncate text-sm">
              {user.username}
            </span>
          </div>
          <button
            onClick={onLogout}
            className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted"
          >
            退出
          </button>
        </div>
      </div>
    </aside>
  );
};
