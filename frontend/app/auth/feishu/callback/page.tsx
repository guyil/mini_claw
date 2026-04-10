"use client";

import { saveAuth } from "@/lib/auth";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function FeishuCallbackInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    const code = params.get("code");
    const state = params.get("state") ?? "";
    if (!code) {
      setError("缺少飞书授权码");
      return;
    }

    const isFromChat = state.startsWith("chat_");
    let cancelled = false;

    async function exchangeCode() {
      try {
        const resp = await fetch("/api/auth/feishu/callback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code }),
        });

        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          throw new Error(data.detail || `登录失败 (${resp.status})`);
        }

        const data = await resp.json();
        if (!cancelled) {
          saveAuth(data.access_token, {
            user_id: data.user_id,
            username: data.display_name || data.username,
          });

          if (isFromChat) {
            setSuccess(true);
            setTimeout(() => {
              window.close();
            }, 2000);
          } else {
            router.replace("/");
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "飞书登录失败");
        }
      }
    }

    exchangeCode();
    return () => {
      cancelled = true;
    };
  }, [params, router]);

  if (error) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-4">
        <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-8 shadow-lg">
          <div className="flex size-12 items-center justify-center rounded-full bg-red-100 text-red-600">
            <svg className="size-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <p className="text-destructive">{error}</p>
          <a href="/" className="text-sm text-muted-foreground underline">
            返回首页
          </a>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-4">
        <div className="flex flex-col items-center gap-3 rounded-2xl border bg-card p-8 shadow-lg">
          <div className="flex size-12 items-center justify-center rounded-full bg-green-100 text-green-600">
            <svg className="size-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-lg font-medium">飞书授权成功！</p>
          <p className="text-sm text-muted-foreground">
            请回到对话窗口继续操作，此页面将自动关闭。
          </p>
          <a href="/" className="mt-2 text-sm text-blue-600 underline">
            如未自动关闭，点击返回
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-dvh items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <svg className="size-6 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        <p className="text-muted-foreground">飞书授权中...</p>
      </div>
    </div>
  );
}

export default function FeishuCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-dvh items-center justify-center">
          <p className="text-muted-foreground">加载中...</p>
        </div>
      }
    >
      <FeishuCallbackInner />
    </Suspense>
  );
}
