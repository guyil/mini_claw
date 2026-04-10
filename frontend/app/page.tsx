"use client";

import { MyRuntimeProvider } from "./MyRuntimeProvider";
import { ChatPanel } from "@/components/ChatPanel";
import { Sidebar } from "@/components/Sidebar";
import { clearAuth, getToken, getUser, type UserInfo } from "@/lib/auth";
import type { LangChainMessage } from "@assistant-ui/react-langgraph";
import { useCallback, useEffect, useState } from "react";

interface ConversationItem {
  id: string;
  title: string;
  created_at: string | null;
  updated_at: string | null;
}

export default function Home() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historyMessages, setHistoryMessages] = useState<LangChainMessage[]>([]);
  const [historyLoadedFor, setHistoryLoadedFor] = useState<string | null>(null);

  useEffect(() => {
    setUser(getUser());
    setToken(getToken());
  }, []);

  const fetchConversations = useCallback(async () => {
    if (!token) return;
    try {
      const resp = await fetch("/api/conversations", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (resp.ok) {
        const data = await resp.json();
        setConversations(data);
      }
    } catch {
      /* ignore */
    }
  }, [token]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  useEffect(() => {
    if (!activeConvId || !token) {
      setHistoryMessages([]);
      setHistoryLoadedFor(null);
      return;
    }

    let cancelled = false;
    setHistoryLoadedFor(null);

    fetch(`/api/conversations/${activeConvId}/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (!cancelled) {
          setHistoryMessages(data);
          setHistoryLoadedFor(activeConvId);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistoryMessages([]);
          setHistoryLoadedFor(activeConvId);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeConvId, token]);

  useEffect(() => {
    if (token) {
      fetch("/api/user/bot", {
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
  }, [token]);

  const handleLogout = () => {
    clearAuth();
    setUser(null);
    setToken(null);
    setConversations([]);
    setActiveConvId(null);
  };

  const handleNewConversation = async () => {
    if (!token) return;
    try {
      const resp = await fetch("/api/conversations", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title: "新对话" }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setConversations((prev) => [data, ...prev]);
        setActiveConvId(data.id);
      }
    } catch {
      /* ignore */
    }
  };

  const handleDeleteConversation = async (convId: string) => {
    if (!token) return;
    try {
      await fetch(`/api/conversations/${convId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        setActiveConvId(null);
      }
    } catch {
      /* ignore */
    }
  };

  if (!user || !token) {
    return (
      <main className="flex h-dvh items-center justify-center bg-gradient-to-b from-background to-muted/30">
        <div className="flex flex-col items-center gap-6 rounded-2xl border bg-card p-10 shadow-lg">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-xl bg-blue-600 text-xl font-bold text-white">
              爪
            </div>
            <div>
              <h1 className="text-xl font-semibold">AI 助手平台</h1>
              <p className="text-sm text-muted-foreground">
                跨境电商智能助手
              </p>
            </div>
          </div>
          <a
            href="/api/auth/feishu/login"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white shadow-md transition-colors hover:bg-blue-700"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.573 7.093L9.83 12.5l-3.67 3.14-4.66-5.207a1 1 0 0 1 1.073-1.34zm6.927 7.38l3.67-3.14 7.257 5.407a1 1 0 0 1-1.073 1.34l-9.854-3.607zM14.17 12.5L10.5 9.36l9.854-3.607a1 1 0 0 1 1.073 1.34L14.17 12.5z" />
            </svg>
            飞书登录
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-dvh">
      {sidebarOpen && (
        <Sidebar
          conversations={conversations}
          activeConvId={activeConvId}
          onSelect={setActiveConvId}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          onClose={() => setSidebarOpen(false)}
          user={user}
          onLogout={handleLogout}
        />
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b px-4 py-2.5">
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
              title="展开侧栏"
            >
              <svg
                className="size-5"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
                />
              </svg>
            </button>
          )}
          <h1 className="text-sm font-medium text-muted-foreground">
            {conversations.find((c) => c.id === activeConvId)?.title ||
              "AI 助手"}
          </h1>
        </header>

        <div className="flex-1 overflow-hidden">
          {activeConvId && historyLoadedFor !== activeConvId ? (
            <div className="flex h-full items-center justify-center">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <svg className="size-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                加载对话历史...
              </div>
            </div>
          ) : (
            <MyRuntimeProvider
              key={activeConvId ?? "default"}
              token={token}
              threadId={activeConvId}
              initialMessages={historyMessages}
            >
              <ChatPanel />
            </MyRuntimeProvider>
          )}
        </div>
      </div>
    </main>
  );
}
