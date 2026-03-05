"use client";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import type { ToolUIPart } from "ai";

import {
  Attachment,
  AttachmentPreview,
  AttachmentRemove,
  Attachments,
} from "@/components/ai-elements/attachments";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageBranch,
  MessageBranchContent,
  MessageBranchNext,
  MessageBranchPage,
  MessageBranchPrevious,
  MessageBranchSelector,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import {
  ModelSelector,
  ModelSelectorContent,
  ModelSelectorEmpty,
  ModelSelectorGroup,
  ModelSelectorInput,
  ModelSelectorItem,
  ModelSelectorList,
  ModelSelectorLogo,
  ModelSelectorLogoGroup,
  ModelSelectorName,
  ModelSelectorTrigger,
} from "@/components/ai-elements/model-selector";

import {
  ModelSelector as CategorySelector,
  ModelSelectorContent as CategorySelectorContent,
  ModelSelectorEmpty as CategorySelectorEmpty,
  ModelSelectorGroup as CategorySelectorGroup,
  ModelSelectorInput as CategorySelectorInput,
  ModelSelectorItem as CategorySelectorItem,
  ModelSelectorList as CategorySelectorList,
  ModelSelectorName as CategorySelectorName,
  ModelSelectorTrigger as CategorySelectorTrigger,
} from "@/components/ai-elements/model-selector";
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputHeader,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputTools,
  usePromptInputAttachments,
} from "@/components/ai-elements/prompt-input";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Source,
  Sources,
  SourcesContent,
  SourcesTrigger,
} from "@/components/ai-elements/sources";
import { SpeechInput } from "@/components/ai-elements/speech-input";
import { Suggestion, Suggestions } from "@/components/ai-elements/suggestion";
import { BrainIcon, CheckIcon, GlobeIcon, MenuIcon, MessageCircleIcon, LibraryIcon } from "lucide-react";
import { nanoid } from "nanoid";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface MessageType {
  key: string;
  from: "user" | "assistant";
  sources?: { href: string; title: string }[];
  versions: {
    id: string;
    content: string;
  }[];
  reasoning?: {
    content: string;
    duration: number;
  };
  tools?: {
    toolCallId: string;
    type: `tool-${string}`;
    state: ToolUIPart["state"];
    input: Record<string, unknown>;
    output: string | undefined;
    errorText: string | undefined;
  }[];
}

const initialMessages: MessageType[] = [
  {
    from: "assistant",
    key: nanoid(),
    versions: [
      {
        content: "Ask a question to start chatting.",
        id: nanoid(),
      },
    ],
  },
];

const models = [
  {
    chef: "OpenAI",
    chefSlug: "openai",
    id: "gpt-4o",
    name: "GPT-4o",
    providers: ["openai", "azure"],
  },
  {
    chef: "OpenAI",
    chefSlug: "openai",
    id: "gpt-4o-mini",
    name: "GPT-4o Mini",
    providers: ["openai", "azure"],
  },
  {
    chef: "Anthropic",
    chefSlug: "anthropic",
    id: "claude-opus-4-20250514",
    name: "Claude 4 Opus",
    providers: ["anthropic", "azure", "google", "amazon-bedrock"],
  },
  {
    chef: "Anthropic",
    chefSlug: "anthropic",
    id: "claude-sonnet-4-20250514",
    name: "Claude 4 Sonnet",
    providers: ["anthropic", "azure", "google", "amazon-bedrock"],
  },
  {
    chef: "Google",
    chefSlug: "google",
    id: "gemini-2.0-flash-exp",
    name: "Gemini 2.0 Flash",
    providers: ["google"],
  },
];

const suggestions: string[] = [];

type ChatStreamChunk = {
  type?: "delta" | "status" | "final";
  is_task_complete?: boolean;
  updates?: string;
  delta?: string;
  content?: string;
  suggestions?: string; // JSON string from backend
};

type ToolEvent = {
  toolCallId: string;
  type: `tool-${string}`;
  state: ToolUIPart["state"];
  input: Record<string, unknown>;
  output: string | undefined;
  errorText: string | undefined;
};

const parseBackendStatus = (
  raw: string
):
  | { kind: "tool-call"; toolName: string; args: Record<string, unknown> }
  | { kind: "tool-result"; toolName: string; result: string }
  | { kind: "status"; text: string }
  | { kind: "ignore" } => {
  const text = String(raw || "").trim();

  // Ignore generic model lifecycle logs (they are not tool usage).
  if (
    /^Model processing:/i.test(text) ||
    /^Model responded:/i.test(text) ||
    /^Model metadata:/i.test(text)
  ) {
    return { kind: "ignore" };
  }

  // Example: "Model calling tool: semantic_search with args {'query': '...', 'top_k': 3}"
  const callMatch = text.match(
    /^Model calling tool:\s*([^\s]+)\s*with args\s*(\{[\s\S]*\})\s*$/
  );
  if (callMatch) {
    const toolName = callMatch[1];
    const argsRaw = callMatch[2];
    // Backend uses Python dict formatting sometimes; normalize to JSON.
    const normalized = argsRaw
      .replace(/\bNone\b/g, "null")
      .replace(/\bTrue\b/g, "true")
      .replace(/\bFalse\b/g, "false")
      .replace(/'/g, '"');
    try {
      const args = JSON.parse(normalized) as Record<string, unknown>;
      return { kind: "tool-call", toolName, args };
    } catch {
      return { kind: "tool-call", toolName, args: { raw: argsRaw } };
    }
  }

  // Example: "Tool semantic_search responded with: ..."
  const resultMatch = text.match(/^Tool\s+([^\s]+)\s+responded with:\s*([\s\S]*)$/);
  if (resultMatch) {
    return {
      kind: "tool-result",
      toolName: resultMatch[1],
      result: (resultMatch[2] || "").trim(),
    };
  }

  return { kind: "status", text };
};

const API_BASE = process.env.NEXT_PUBLIC_CHAT_API_BASE || "http://localhost:8000";

const SELECTED_CATEGORIES_STORAGE_KEY = "rag.selectedCategories";

const delay = (ms: number): Promise<void> =>
  // eslint-disable-next-line promise/avoid-new -- setTimeout requires a new Promise
  new Promise((resolve) => {
    setTimeout(resolve, ms);
  });

const chefs = ["OpenAI", "Anthropic", "Google"];

const AttachmentItem = ({
  attachment,
  onRemove,
}: {
  // Keep this loose because `usePromptInputAttachments().files` is FileUIPart-based,
  // while the Attachment component expects its own AttachmentData shape.
  attachment: any;
  onRemove: (id: string) => void;
}) => {
  const handleRemove = useCallback(() => {
    onRemove(attachment.id);
  }, [onRemove, attachment.id]);

  return (
    <Attachment data={attachment} onRemove={handleRemove}>
      <AttachmentPreview />
      <AttachmentRemove />
    </Attachment>
  );
};

const PromptInputAttachmentsDisplay = () => {
  const attachments = usePromptInputAttachments();

  const handleRemove = useCallback(
    (id: string) => {
      attachments.remove(id);
    },
    [attachments]
  );

  if (attachments.files.length === 0) {
    return null;
  }

  return (
    <Attachments variant="inline">
      {attachments.files.map((attachment) => (
        <AttachmentItem
          attachment={attachment as any}
          key={attachment.id}
          onRemove={handleRemove}
        />
      ))}
    </Attachments>
  );
};

const SuggestionItem = ({
  suggestion,
  onClick,
}: {
  suggestion: string;
  onClick: (suggestion: string) => void;
}) => {
  const handleClick = useCallback(() => {
    onClick(suggestion);
  }, [onClick, suggestion]);

  return <Suggestion onClick={handleClick} suggestion={suggestion} />;
};

const ModelItem = ({
  m,
  isSelected,
  onSelect,
}: {
  m: (typeof models)[0];
  isSelected: boolean;
  onSelect: (id: string) => void;
}) => {
  const handleSelect = useCallback(() => {
    onSelect(m.id);
  }, [onSelect, m.id]);

  return (
    <ModelSelectorItem onSelect={handleSelect} value={m.id}>
      <ModelSelectorLogo provider={m.chefSlug} />
      <ModelSelectorName>{m.name}</ModelSelectorName>
      <ModelSelectorLogoGroup>
        {m.providers.map((provider) => (
          <ModelSelectorLogo key={provider} provider={provider} />
        ))}
      </ModelSelectorLogoGroup>
      {isSelected ? (
        <CheckIcon className="ml-auto size-4" />
      ) : (
        <div className="ml-auto size-4" />
      )}
    </ModelSelectorItem>
  );
};

const Example = () => {
  const [navOpen, setNavOpen] = useState(false);
  const [model, setModel] = useState<string>(models[0].id);
  const [modelSelectorOpen, setModelSelectorOpen] = useState(false);
  const [text, setText] = useState<string>("");
  const [useWebSearch, setUseWebSearch] = useState<boolean>(false);
  const [status, setStatus] = useState<
    "submitted" | "streaming" | "ready" | "error"
  >("ready");
  const [messages, setMessages] = useState<MessageType[]>(initialMessages);
  const [, setStreamingMessageId] = useState<string | null>(null);

  const [availableCategories, setAvailableCategories] = useState<string[]>([]);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [categorySelectorOpen, setCategorySelectorOpen] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SELECTED_CATEGORIES_STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as unknown;
        if (Array.isArray(parsed)) {
          setSelectedCategories(parsed.map((c) => String(c)).filter((c) => c.trim()));
        }
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/knowledge/categories`);
        if (!res.ok) return;
        const data = (await res.json()) as { categories?: unknown };
        if (cancelled) return;
        const cats = Array.isArray(data.categories)
          ? (data.categories.map((c) => String(c)) as string[])
          : [];
        setAvailableCategories(cats);
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(
        SELECTED_CATEGORIES_STORAGE_KEY,
        JSON.stringify(selectedCategories)
      );
    } catch {
      // ignore
    }
  }, [selectedCategories]);

  const toggleCategory = useCallback((cat: string) => {
    const c = String(cat).trim();
    if (!c) return;
    setSelectedCategories((prev) =>
      prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]
    );
  }, []);

  const clearCategories = useCallback(() => {
    setSelectedCategories([]);
  }, []);

  const selectedCategoryLabel = useMemo(() => {
    if (!selectedCategories.length) return "All categories";
    if (selectedCategories.length === 1) return selectedCategories[0];
    return `${selectedCategories.length} categories`;
  }, [selectedCategories]);

  const selectedModelData = useMemo(
    () => models.find((m) => m.id === model),
    [model]
  );

  const updateMessageContent = useCallback(
    (messageId: string, newContent: string) => {
      setMessages((prev) =>
        prev.map((msg) => {
          if (msg.versions.some((v) => v.id === messageId)) {
            return {
              ...msg,
              versions: msg.versions.map((v) =>
                v.id === messageId ? { ...v, content: newContent } : v
              ),
            };
          }
          return msg;
        })
      );
    },
    []
  );

  const appendToolEvent = useCallback(
    (messageId: string, toolEvent: ToolEvent) => {
      setMessages((prev) =>
        prev.map((msg) => {
          if (!msg.versions.some((v) => v.id === messageId)) {
            return msg;
          }

          const existing = msg.tools ?? [];
          const idx = existing.findIndex((t) => t.toolCallId === toolEvent.toolCallId);
          const next = idx >= 0
            ? existing.map((t, i) => (i === idx ? toolEvent : t))
            : [...existing, toolEvent];

          return { ...msg, tools: next };
        })
      );
    },
    []
  );

  const streamResponse = useCallback(
    async (messageId: string, content: string) => {
      setStatus("streaming");
      setStreamingMessageId(messageId);

      updateMessageContent(messageId, "");
      // Backend currently exposes only POST /chat (per /openapi.json),
      // so use fetch + streamed response body (works without SSE route).
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: content,
          session_id: String(Date.now()),
          categories: selectedCategories,
        }),
      });

      if (!res.ok || !res.body) {
        setStatus("error");
        setStreamingMessageId(null);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assembled = "";
      let toolSeq = 0;
      const toolIdByName = new Map<string, string>();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // NDJSON: one JSON object per line
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const chunk = JSON.parse(line) as ChatStreamChunk;

            if (chunk.delta) {
              assembled += String(chunk.delta);
              updateMessageContent(messageId, assembled);
            } else if (chunk.updates) {
              const parsed = parseBackendStatus(String(chunk.updates));

              if (parsed.kind === "tool-call") {
                toolSeq += 1;
                const toolCallId = `${messageId}-tool-${toolSeq}`;
                toolIdByName.set(parsed.toolName, toolCallId);
                appendToolEvent(messageId, {
                  toolCallId,
                  type: `tool-${parsed.toolName}`,
                  state: "input-available",
                  input: parsed.args,
                  output: undefined,
                  errorText: undefined,
                });
              } else if (parsed.kind === "tool-result") {
                const existingId = toolIdByName.get(parsed.toolName);
                const toolCallId = existingId ?? `${messageId}-tool-${parsed.toolName}`;
                appendToolEvent(messageId, {
                  toolCallId,
                  type: `tool-${parsed.toolName}`,
                  state: "output-available",
                  input: {},
                  output: parsed.result,
                  errorText: undefined,
                });
              } else {
                // Generic status line: ignore (regular chat should stay clean).
                if (parsed.kind !== "ignore") {
                  // Intentionally no-op
                }
              }
            }

            if (chunk.is_task_complete) {
              if (chunk.content) {
                updateMessageContent(messageId, String(chunk.content));
              }

              if (chunk.suggestions) {
                try {
                  const parsed = JSON.parse(chunk.suggestions) as {
                    suggested_questions?: string[];
                  };
                  if (parsed?.suggested_questions?.length) {
                    setFollowups(parsed.suggested_questions);
                  }
                } catch {
                  // ignore
                }
              }
            }
          } catch {
            // ignore malformed line
          }
        }
      }

      setStatus("ready");
      setStreamingMessageId(null);
      return;

    },
    [appendToolEvent, selectedCategories, updateMessageContent]
  );

  const addUserMessage = useCallback(
    (content: string) => {
      const userMessageId = `user-${Date.now()}`;
      const userMessage: MessageType = {
        from: "user",
        key: userMessageId,
        versions: [{ content, id: userMessageId }],
      };

      const assistantMessageId = `assistant-${Date.now()}`;
      const assistantMessage: MessageType = {
        from: "assistant",
        key: assistantMessageId,
        versions: [{ content: "", id: assistantMessageId }],
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      streamResponse(assistantMessageId, content);
    },
    [streamResponse]
  );

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const hasText = Boolean(message.text);
      const hasAttachments = Boolean(message.files?.length);

      if (!(hasText || hasAttachments)) {
        return;
      }

      setStatus("submitted");

      if (message.files?.length) {
        toast.success("Files attached", {
          description: `${message.files.length} file(s) attached to message`,
        });
      }

      addUserMessage(message.text || "Sent with attachments");
      setText("");
    },
    [addUserMessage]
  );

  const handleSuggestionClick = useCallback(
    (suggestion: string) => {
      setStatus("submitted");
      addUserMessage(suggestion);
    },
    [addUserMessage]
  );

  const handleTranscriptionChange = useCallback((transcript: string) => {
    setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
  }, []);

  const handleTextChange = useCallback(
    (event: React.ChangeEvent<HTMLTextAreaElement>) => {
      setText(event.target.value);
    },
    []
  );

  const toggleWebSearch = useCallback(() => {
    setUseWebSearch((prev) => !prev);
  }, []);

  const toggleNav = useCallback(() => {
    setNavOpen((v) => !v);
  }, []);

  const handleModelSelect = useCallback((modelId: string) => {
    setModel(modelId);
    setModelSelectorOpen(false);
  }, []);

  const [followups, setFollowups] = useState<string[]>([]);

  const isSubmitDisabled = useMemo(
    () => !text.trim() || status === "streaming",
    [text, status]
  );

  return (
    <div className="relative flex h-dvh w-full flex-col overflow-hidden bg-gradient-to-b from-red-50 via-white to-slate-50 text-slate-900">
      <header className="shrink-0 border-b border-red-200/70 bg-white/80 px-3 py-2 backdrop-blur">
        <div className="flex items-center gap-2">
          <PromptInputButton
            aria-label="Open menu"
            onClick={toggleNav}
            variant="ghost"
            className="text-slate-700 hover:bg-red-50"
          >
            <MenuIcon size={18} />
          </PromptInputButton>

          <div className="flex items-center gap-2">
            <div className="grid size-8 place-items-center rounded-xl bg-[#C74634]/10 text-[#C74634] ring-1 ring-[#C74634]/20">
              <MessageCircleIcon className="size-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-slate-900">Chat</div>
              <div className="text-[11px] text-slate-500">
                Oracle Redwood theme
              </div>
            </div>
          </div>
        </div>

        {navOpen ? (
          <div className="mt-2 rounded-2xl border border-red-200/70 bg-white shadow-sm">
            <nav className="grid p-2 text-sm">
              <a
                className="flex items-center gap-2 rounded-xl px-3 py-2 font-semibold text-slate-900 hover:bg-red-50"
                href="/"
              >
                <MessageCircleIcon className="size-4 text-[#C74634]" />
                Chat
              </a>
              <a
                className="flex items-center gap-2 rounded-xl px-3 py-2 font-semibold text-slate-900 hover:bg-red-50"
                href="/knowledge"
              >
                <LibraryIcon className="size-4 text-[#C74634]" />
                Knowledge
              </a>
            </nav>
          </div>
        ) : null}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <Conversation>
          <ConversationContent>
          {messages.map(({ versions, ...message }) => (
            <MessageBranch defaultBranch={0} key={message.key}>
              <MessageBranchContent>
                {versions.map((version) => (
                  <Message
                    from={message.from}
                    key={`${message.key}-${version.id}`}
                  >
                    <div>
                      {message.sources?.length && (
                        <Sources>
                          <SourcesTrigger count={message.sources.length} />
                          <SourcesContent>
                            {message.sources.map((source) => (
                              <Source
                                href={source.href}
                                key={source.href}
                                title={source.title}
                              />
                            ))}
                          </SourcesContent>
                        </Sources>
                      )}
                      {message.reasoning && (
                        <Reasoning duration={message.reasoning.duration}>
                          <ReasoningTrigger />
                          <ReasoningContent>
                            {message.reasoning.content}
                          </ReasoningContent>
                        </Reasoning>
                      )}
                      <MessageContent>
                        <div className="prose prose-slate max-w-none prose-pre:rounded-xl prose-pre:border prose-pre:border-slate-200 prose-pre:bg-slate-950 prose-pre:text-slate-50 prose-code:text-[#C74634]">
                          <MessageResponse>{version.content}</MessageResponse>
                        </div>
                      </MessageContent>
                      {message.tools?.length ? (
                        <div className="not-prose mt-3 space-y-2">
                          {message.tools.map((t) => (
                            <Tool key={t.toolCallId} defaultOpen={false}>
                              <ToolHeader
                                type={t.type as ToolUIPart["type"]}
                                state={t.state}
                                title={t.type.replace(/^tool-/, "")}
                              />
                              <ToolContent>
                                <ToolInput input={t.input} />
                                <ToolOutput output={t.output} errorText={t.errorText} />
                              </ToolContent>
                            </Tool>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  </Message>
                ))}
              </MessageBranchContent>
              {versions.length > 1 && (
                <MessageBranchSelector>
                  <MessageBranchPrevious />
                  <MessageBranchPage />
                  <MessageBranchNext />
                </MessageBranchSelector>
              )}
            </MessageBranch>
          ))}
        </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
      </div>

      <div className="grid shrink-0 gap-4 border-t border-red-200/70 bg-white/80 px-4 pb-4 pt-4 backdrop-blur">
        <Suggestions className="px-0">
          {(followups.length ? followups : suggestions).map((suggestion) => (
            <SuggestionItem
              key={suggestion}
              onClick={handleSuggestionClick}
              suggestion={suggestion}
            />
          ))}
        </Suggestions>

        <div className="w-full rounded-3xl border border-red-200/70 bg-gradient-to-b from-white to-red-50/40 p-3 shadow-sm">
          <PromptInput globalDrop multiple onSubmit={handleSubmit}>
            <PromptInputHeader>
              <PromptInputAttachmentsDisplay />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <CategorySelector
                  open={categorySelectorOpen}
                  onOpenChange={setCategorySelectorOpen}
                >
                  <CategorySelectorTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-2"
                    >
                      <BrainIcon size={16} />
                      <CategorySelectorName>{selectedCategoryLabel}</CategorySelectorName>
                      {selectedCategories.length > 0 ? (
                        <Badge variant="secondary">{selectedCategories.length}</Badge>
                      ) : null}
                    </Button>
                  </CategorySelectorTrigger>

                  <CategorySelectorContent title="Knowledge Categories">
                    <CategorySelectorInput placeholder="Search categories..." />
                    <CategorySelectorList>
                      <CategorySelectorEmpty>No categories found.</CategorySelectorEmpty>
                      <CategorySelectorGroup heading="Knowledge">
                        <CategorySelectorItem
                          onSelect={() => {
                            clearCategories();
                            setCategorySelectorOpen(false);
                          }}
                          value="__all__"
                        >
                          <span className="mr-2 inline-flex size-4 items-center justify-center">
                            {selectedCategories.length === 0 ? (
                              <CheckIcon className="size-4" />
                            ) : null}
                          </span>
                          All categories
                        </CategorySelectorItem>
                        {availableCategories.map((cat) => {
                          const active = selectedCategories.includes(cat);
                          return (
                            <CategorySelectorItem
                              key={cat}
                              onSelect={() => toggleCategory(cat)}
                              value={cat}
                            >
                              <span className="mr-2 inline-flex size-4 items-center justify-center">
                                {active ? <CheckIcon className="size-4" /> : null}
                              </span>
                              {cat}
                            </CategorySelectorItem>
                          );
                        })}
                      </CategorySelectorGroup>
                    </CategorySelectorList>
                  </CategorySelectorContent>
                </CategorySelector>

                <span className="text-xs text-slate-500">
                  If none selected, chat searches across all knowledge.
                </span>
              </div>
            </PromptInputHeader>
            <PromptInputBody>
              <PromptInputTextarea onChange={handleTextChange} value={text} />
            </PromptInputBody>
            <PromptInputFooter>
              <PromptInputTools>
                <PromptInputActionMenu>
                  <PromptInputActionMenuTrigger />
                  <PromptInputActionMenuContent>
                    <PromptInputActionAddAttachments />
                  </PromptInputActionMenuContent>
                </PromptInputActionMenu>
                <SpeechInput
                  className="shrink-0"
                  onTranscriptionChange={handleTranscriptionChange}
                  size="icon-sm"
                  variant="ghost"
                />
                <PromptInputButton
                  onClick={toggleWebSearch}
                  variant={useWebSearch ? "default" : "ghost"}
                  className={
                    useWebSearch ? "bg-[#C74634] hover:bg-[#B33C2D]" : ""
                  }
                >
                  <GlobeIcon size={16} />
                  <span>Search</span>
                </PromptInputButton>
                <ModelSelector
                  onOpenChange={setModelSelectorOpen}
                  open={modelSelectorOpen}
                >
                  <ModelSelectorTrigger asChild>
                    <PromptInputButton className="border border-slate-200 bg-white text-slate-800 shadow-sm hover:bg-slate-50">
                      {selectedModelData?.chefSlug && (
                        <ModelSelectorLogo provider={selectedModelData.chefSlug} />
                      )}
                      {selectedModelData?.name && (
                        <ModelSelectorName>{selectedModelData.name}</ModelSelectorName>
                      )}
                    </PromptInputButton>
                  </ModelSelectorTrigger>
                  <ModelSelectorContent>
                    <ModelSelectorInput placeholder="Search models..." />
                    <ModelSelectorList>
                      <ModelSelectorEmpty>
                        No models found.
                      </ModelSelectorEmpty>
                      {chefs.map((chef) => (
                        <ModelSelectorGroup heading={chef} key={chef}>
                          {models
                            .filter((m) => m.chef === chef)
                            .map((m) => (
                              <ModelItem
                                isSelected={model === m.id}
                                key={m.id}
                                m={m}
                                onSelect={handleModelSelect}
                              />
                            ))}
                        </ModelSelectorGroup>
                      ))}
                    </ModelSelectorList>
                  </ModelSelectorContent>
                </ModelSelector>
              </PromptInputTools>
              <PromptInputSubmit disabled={isSubmitDisabled} status={status} />
            </PromptInputFooter>
          </PromptInput>
        </div>
      </div>
    </div>
  );
};

export default Example;
