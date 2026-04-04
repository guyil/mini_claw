"use client";

import { saveAuth } from "@/lib/auth";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function FeishuCallbackInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = params.get("code");
    if (!code) {
      setError("缺少飞书授权码");
      return;
    }

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
          router.replace("/");
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
        <p className="text-destructive">{error}</p>
        <a href="/" className="text-sm text-muted-foreground underline">
          返回首页
        </a>
      </div>
    );
  }

  return (
    <div className="flex h-dvh items-center justify-center">
      <p className="text-muted-foreground">飞书登录中...</p>
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
