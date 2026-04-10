"use client";

import {
  AssistantRuntimeProvider,
  type AssistantTransportConnectionMetadata,
  unstable_createMessageConverter as createMessageConverter,
  useAssistantTransportRuntime,
} from "@assistant-ui/react";
import {
  convertLangChainMessages,
  type LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { type ReactNode, useMemo } from "react";

type AgentState = {
  messages: LangChainMessage[];
};

const langChainConverter = createMessageConverter(convertLangChainMessages);

const converter = (
  state: AgentState,
  connectionMetadata: AssistantTransportConnectionMetadata,
) => {
  const optimisticMessages = connectionMetadata.pendingCommands.flatMap(
    (c): LangChainMessage[] => {
      if (c.type === "add-message") {
        return [
          {
            type: "human" as const,
            content: [
              {
                type: "text" as const,
                text: c.message.parts
                  .map((p) => (p.type === "text" ? p.text : ""))
                  .join("\n"),
              },
            ],
          },
        ];
      }
      return [];
    },
  );

  const messages = [...(state.messages ?? []), ...optimisticMessages];

  return {
    messages: langChainConverter.toThreadMessages(messages),
    isRunning: connectionMetadata.isSending || false,
  };
};

export function MyRuntimeProvider({
  children,
  token,
  threadId,
  initialMessages,
}: Readonly<{
  children: ReactNode;
  token?: string | null;
  threadId?: string | null;
  initialMessages?: LangChainMessage[];
}>) {
  const headers = useMemo((): Record<string, string> => {
    if (token) return { Authorization: `Bearer ${token}` };
    return {};
  }, [token]);

  const restoredState = useMemo(
    (): AgentState => ({ messages: initialMessages ?? [] }),
    [initialMessages],
  );

  const runtime = useAssistantTransportRuntime({
    initialState: restoredState,
    api: "/api/assistant",
    converter,
    headers,
    body: {
      threadId: threadId ?? undefined,
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
