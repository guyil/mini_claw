"use client";

import { getToken, getUser } from "@/lib/auth";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

interface SkillInfo {
  id: string;
  name: string;
  display_name?: string;
  description?: string;
  category?: string;
  version?: string;
  instructions?: string;
  required_tools?: string[];
  scope?: string;
  is_active: boolean;
}

interface MemoryItem {
  id: string;
  type: string;
  content: string;
  source: string | null;
  importance: number;
  memory_date: string | null;
  created_at: string | null;
  expires_at: string | null;
}

interface AgentInfo {
  id: string;
  name: string;
  is_active: boolean;
  model_name: string;
  temperature: number;
  soul: string;
  instructions: string | null;
  user_context: string | null;
  created_at: string | null;
  updated_at: string | null;
  owner: {
    id: string;
    username: string;
    display_name: string | null;
    email: string;
  } | null;
  skills: SkillInfo[];
  memory_stats: Record<string, number>;
  conversation_count: number;
}

function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "muted";
}) {
  const cls = {
    default:
      "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800",
    success:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800",
    warning:
      "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800",
    muted:
      "bg-muted text-muted-foreground border-border",
  }[variant];

  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${cls}`}
    >
      {children}
    </span>
  );
}

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border bg-card p-3">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        {icon}
      </div>
      <div>
        <div className="text-lg font-semibold leading-none">{value}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

function CollapsibleText({
  text,
  maxLines = 3,
  label,
}: {
  text: string;
  maxLines?: number;
  label: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const lines = text.split("\n");
  const needsCollapse = lines.length > maxLines;

  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted-foreground">
        {label}
      </div>
      <div className="rounded-md border bg-muted/30 p-3">
        <pre
          className={`whitespace-pre-wrap text-xs leading-relaxed ${
            !expanded && needsCollapse ? `line-clamp-${maxLines}` : ""
          }`}
          style={
            !expanded && needsCollapse
              ? {
                  display: "-webkit-box",
                  WebkitLineClamp: maxLines,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }
              : undefined
          }
        >
          {text}
        </pre>
        {needsCollapse && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-1.5 text-xs font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            {expanded ? "收起" : "展开全部"}
          </button>
        )}
      </div>
    </div>
  );
}

function memoryTypeLabel(type: string) {
  return type === "long_term"
    ? "长期记忆"
    : type === "daily"
      ? "日常记忆"
      : type === "fact"
        ? "事实"
        : type;
}

function memoryTypeColor(type: string) {
  return type === "long_term"
    ? "bg-blue-500"
    : type === "daily"
      ? "bg-emerald-500"
      : "bg-amber-500";
}

function SkillDetailDialog({
  skill,
  open,
  onOpenChange,
}: {
  skill: SkillInfo;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <DialogTitle>{skill.display_name || skill.name}</DialogTitle>
            <Badge variant={skill.is_active ? "success" : "muted"}>
              {skill.is_active ? "启用" : "停用"}
            </Badge>
          </div>
          <DialogDescription>{skill.description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* 基础信息 */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-md border bg-muted/30 p-2.5">
              <div className="text-xs text-muted-foreground">标识名</div>
              <div className="mt-0.5 text-sm font-medium font-mono">{skill.name}</div>
            </div>
            {skill.category && (
              <div className="rounded-md border bg-muted/30 p-2.5">
                <div className="text-xs text-muted-foreground">分类</div>
                <div className="mt-0.5 text-sm font-medium">{skill.category}</div>
              </div>
            )}
            {skill.version && (
              <div className="rounded-md border bg-muted/30 p-2.5">
                <div className="text-xs text-muted-foreground">版本</div>
                <div className="mt-0.5 text-sm font-medium">v{skill.version}</div>
              </div>
            )}
            {skill.scope && (
              <div className="rounded-md border bg-muted/30 p-2.5">
                <div className="text-xs text-muted-foreground">范围</div>
                <div className="mt-0.5 text-sm font-medium">{skill.scope}</div>
              </div>
            )}
          </div>

          {/* 依赖工具 */}
          {skill.required_tools && skill.required_tools.length > 0 && (
            <div>
              <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                依赖工具
              </div>
              <div className="flex flex-wrap gap-1.5">
                {skill.required_tools.map((tool) => (
                  <span
                    key={tool}
                    className="rounded-md border bg-muted/50 px-2 py-1 font-mono text-xs"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 指令体 */}
          {skill.instructions && (
            <div>
              <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                Instructions（技能指令）
              </div>
              <div className="max-h-80 overflow-y-auto rounded-md border bg-muted/30 p-3">
                <pre className="whitespace-pre-wrap text-xs leading-relaxed">
                  {skill.instructions}
                </pre>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function MemoryListDialog({
  agentId,
  agentName,
  open,
  onOpenChange,
}: {
  agentId: string;
  agentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const token = getToken();
    if (!token) return;

    setLoading(true);
    fetch(`/api/admin/agents/${agentId}/memories`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setMemories(data))
      .catch(() => setMemories([]))
      .finally(() => setLoading(false));
  }, [open, agentId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{agentName} — 记忆条目</DialogTitle>
          <DialogDescription>共 {memories.length} 条记忆</DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <svg className="size-4 animate-spin text-muted-foreground" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          </div>
        ) : memories.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            暂无记忆条目
          </p>
        ) : (
          <div className="space-y-2 pt-2">
            {memories.map((m) => (
              <div key={m.id} className="rounded-lg border p-3">
                <div className="mb-1.5 flex items-center gap-2">
                  <div className={`size-2 rounded-full ${memoryTypeColor(m.type)}`} />
                  <span className="text-xs font-medium">
                    {memoryTypeLabel(m.type)}
                  </span>
                  {m.source && (
                    <Badge variant="muted">{m.source}</Badge>
                  )}
                  <span className="ml-auto text-xs text-muted-foreground">
                    重要度 {m.importance}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                  {m.content}
                </p>
                <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                  {m.memory_date && (
                    <span>日期: {m.memory_date}</span>
                  )}
                  {m.created_at && (
                    <span>
                      创建: {new Date(m.created_at).toLocaleString("zh-CN")}
                    </span>
                  )}
                  {m.expires_at && (
                    <span>
                      过期: {new Date(m.expires_at).toLocaleString("zh-CN")}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  const totalMemories = Object.values(agent.memory_stats).reduce(
    (sum, n) => sum + n,
    0,
  );
  const [selectedSkill, setSelectedSkill] = useState<SkillInfo | null>(null);
  const [memoryDialogOpen, setMemoryDialogOpen] = useState(false);

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      {/* 卡片头部 */}
      <div className="flex items-start justify-between border-b px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-blue-600 text-lg font-bold text-white">
            {agent.name.charAt(0)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold">{agent.name}</h3>
              <Badge variant={agent.is_active ? "success" : "muted"}>
                {agent.is_active ? "活跃" : "停用"}
              </Badge>
            </div>
            <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span>{agent.model_name}</span>
              <span>·</span>
              <span>温度 {agent.temperature}</span>
            </div>
          </div>
        </div>
        {agent.owner && (
          <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-3 py-1.5">
            <div className="flex size-6 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
              {(
                agent.owner.display_name || agent.owner.username
              )
                .charAt(0)
                .toUpperCase()}
            </div>
            <div className="text-xs">
              <div className="font-medium">
                {agent.owner.display_name || agent.owner.username}
              </div>
              <div className="text-muted-foreground">{agent.owner.email}</div>
            </div>
          </div>
        )}
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-4 gap-3 border-b px-5 py-4">
        <StatCard
          label="技能"
          value={agent.skills.length}
          icon={
            <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          }
        />
        <StatCard
          label="记忆条目"
          value={totalMemories}
          icon={
            <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
            </svg>
          }
        />
        <StatCard
          label="对话数"
          value={agent.conversation_count}
          icon={
            <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155" />
            </svg>
          }
        />
        <StatCard
          label="创建时间"
          value={
            agent.created_at
              ? new Date(agent.created_at).toLocaleDateString("zh-CN")
              : "-"
          }
          icon={
            <svg className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
            </svg>
          }
        />
      </div>

      {/* Soul / Instructions / User Context */}
      <div className="space-y-3 border-b px-5 py-4">
        {agent.soul && (
          <CollapsibleText text={agent.soul} label="Soul（人格定义）" />
        )}
        {agent.instructions && (
          <CollapsibleText
            text={agent.instructions}
            label="Instructions（工作指令）"
          />
        )}
        {agent.user_context && (
          <CollapsibleText
            text={agent.user_context}
            label="User Context（用户画像）"
          />
        )}
      </div>

      {/* 技能列表 */}
      {agent.skills.length > 0 && (
        <div className="border-b px-5 py-4">
          <div className="mb-2 text-xs font-medium text-muted-foreground">
            已启用技能
          </div>
          <div className="flex flex-wrap gap-2">
            {agent.skills.map((skill) => (
              <button
                key={skill.id}
                onClick={() => setSelectedSkill(skill)}
                className="flex items-center gap-1.5 rounded-lg border bg-muted/30 px-3 py-1.5 transition-colors hover:border-blue-300 hover:bg-blue-50 dark:hover:border-blue-700 dark:hover:bg-blue-950/50"
                title="点击查看详情"
              >
                <svg className="size-3.5 text-blue-500" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                <span className="text-xs font-medium">
                  {skill.display_name || skill.name}
                </span>
                {skill.category && (
                  <Badge variant="muted">{skill.category}</Badge>
                )}
                {skill.version && (
                  <span className="text-xs text-muted-foreground">
                    v{skill.version}
                  </span>
                )}
              </button>
            ))}
          </div>

          <SkillDetailDialog
            skill={selectedSkill ?? agent.skills[0]}
            open={selectedSkill !== null}
            onOpenChange={(open) => {
              if (!open) setSelectedSkill(null);
            }}
          />
        </div>
      )}

      {/* 记忆分布 */}
      {totalMemories > 0 && (
        <div className="px-5 py-4">
          <div className="mb-2 text-xs font-medium text-muted-foreground">
            记忆分布
          </div>
          <button
            onClick={() => setMemoryDialogOpen(true)}
            className="flex gap-3 rounded-md px-2 py-1 -mx-2 -my-1 transition-colors hover:bg-muted"
            title="点击查看所有记忆条目"
          >
            {Object.entries(agent.memory_stats).map(([type, count]) => (
              <div
                key={type}
                className="flex items-center gap-1.5 text-xs"
              >
                <div className={`size-2 rounded-full ${memoryTypeColor(type)}`} />
                <span className="text-muted-foreground">
                  {memoryTypeLabel(type)}
                </span>
                <span className="font-medium">{count}</span>
              </div>
            ))}
          </button>

          <MemoryListDialog
            agentId={agent.id}
            agentName={agent.name}
            open={memoryDialogOpen}
            onOpenChange={setMemoryDialogOpen}
          />
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setError("请先登录");
      setLoading(false);
      return;
    }

    try {
      const resp = await fetch("/api/admin/agents", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!resp.ok) {
        throw new Error(`请求失败: ${resp.status}`);
      }
      const data = await resp.json();
      setAgents(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const user = getUser();

  if (loading) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <svg className="size-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          加载中...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <div className="flex flex-col items-center gap-4 rounded-xl border bg-card p-8">
          <p className="text-sm text-destructive">{error}</p>
          <Link
            href="/"
            className="text-sm text-blue-600 hover:underline"
          >
            返回首页
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-gradient-to-b from-background to-muted/20">
      {/* 顶部导航 */}
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
                爪
              </div>
              <span className="text-sm font-medium text-muted-foreground">
                AI 助手平台
              </span>
            </Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-sm font-semibold">Agent 管理</h1>
          </div>
          <div className="flex items-center gap-3">
            {user && (
              <span className="text-xs text-muted-foreground">
                {user.username}
              </span>
            )}
            <Link
              href="/"
              className="rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
            >
              返回对话
            </Link>
          </div>
        </div>
      </header>

      {/* 主内容 */}
      <main className="mx-auto max-w-6xl px-6 py-6">
        {/* 概览 */}
        <div className="mb-6 grid grid-cols-3 gap-4">
          <div className="rounded-xl border bg-card p-4">
            <div className="text-2xl font-bold">{agents.length}</div>
            <div className="text-sm text-muted-foreground">Agent 总数</div>
          </div>
          <div className="rounded-xl border bg-card p-4">
            <div className="text-2xl font-bold">
              {agents.filter((a) => a.is_active).length}
            </div>
            <div className="text-sm text-muted-foreground">活跃 Agent</div>
          </div>
          <div className="rounded-xl border bg-card p-4">
            <div className="text-2xl font-bold">
              {agents.reduce((sum, a) => sum + a.conversation_count, 0)}
            </div>
            <div className="text-sm text-muted-foreground">总对话数</div>
          </div>
        </div>

        {/* Agent 列表 */}
        {agents.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border bg-card py-16">
            <svg className="size-12 text-muted-foreground/40" fill="none" stroke="currentColor" strokeWidth={1} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
            </svg>
            <p className="text-sm text-muted-foreground">暂无 Agent</p>
          </div>
        ) : (
          <div className="space-y-4">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
