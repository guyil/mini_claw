"use client";

import { Thread } from "@/components/assistant-ui/thread";

export function ChatPanel() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-3xl h-full">
        <Thread />
      </div>
    </div>
  );
}
