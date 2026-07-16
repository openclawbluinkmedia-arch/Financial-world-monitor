"use client";

import { useState, useRef, useEffect } from "react";
import PageHeader from "../components/PageHeader";
import ImpactBadge from "../components/ImpactBadge";
import ConfidenceBar from "../components/ConfidenceBar";

interface CitationSource {
  evidence_id: string;
  title: string;
  snippet: string;
  source_name: string;
  similarity?: number;
  url?: string;
}

interface CopilotMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: CitationSource[];
  verified_facts?: string[];
  analysis?: string;
  portfolio_relevance?: string;
  uncertainty?: string;
  abstained?: boolean;
  abstention_reason?: string;
}

interface CopilotResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  verified_facts: string[];
  analysis?: string;
  portfolio_relevance?: string;
  uncertainty?: string;
  sources: CitationSource[];
  abstained: boolean;
  abstention_reason?: string;
}

interface Conversation {
  id: string;
  title: string;
  mode: string;
  message_count: number;
}

function renderMessageContent(msg: string): React.ReactNode {
  // Simple markdown-like rendering
  const parts = msg.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-fg font-semibold">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

export default function CopilotPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"market_intelligence" | "portfolio_impact">("market_intelligence");
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [showConversations, setShowConversations] = useState(false);
  const [selectedSource, setSelectedSource] = useState<CitationSource | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchConversations = async () => {
    try {
      const res = await fetch("/api/copilot/conversations");
      setConversations(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMsg: CopilotMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/copilot/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg.content,
          mode,
          conversation_id: conversationId,
        }),
      });
      const data: CopilotResponse = await res.json();
      setConversationId(data.conversation_id);

      const assistantMsg: CopilotMessage = {
        id: data.message_id,
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        verified_facts: data.verified_facts,
        analysis: data.analysis,
        portfolio_relevance: data.portfolio_relevance,
        uncertainty: data.uncertainty,
        abstained: data.abstained,
        abstention_reason: data.abstention_reason,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      fetchConversations();
    } catch (e) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Error: Failed to get response from copilot.",
          abstained: true,
          abstention_reason: "API error",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const loadConversation = async (convId: string) => {
    setConversationId(convId);
    setShowConversations(false);
    setMessages([]);
    setLoading(true);
    try {
      const res = await fetch(`/api/copilot/conversations/${convId}/messages`);
      const msgs: CopilotMessage[] = await res.json();
      setMessages(msgs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const hasSources = messages.some((m) => (m.sources?.length ?? 0) > 0);

  return (
    <div className="flex h-[calc(100vh-0px)]">
      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-4 border-b border-surface-border">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-fg">Copilot</h1>
              <p className="text-xs text-fg-dim mt-0.5">
                AI-powered financial intelligence assistant
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Mode toggle */}
              <div className="flex bg-surface-alt rounded-lg border border-surface-border p-0.5">
                <button
                  onClick={() => setMode("market_intelligence")}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                    mode === "market_intelligence"
                      ? "bg-surface-hover text-fg font-medium"
                      : "text-fg-dim hover:text-fg"
                  }`}
                >
                  Market Intel
                </button>
                <button
                  onClick={() => setMode("portfolio_impact")}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                    mode === "portfolio_impact"
                      ? "bg-surface-hover text-fg font-medium"
                      : "text-fg-dim hover:text-fg"
                  }`}
                >
                  Portfolio
                </button>
              </div>
              <button
                onClick={() => setShowConversations(!showConversations)}
                className="btn-ghost text-xs"
              >
                History
              </button>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-4xl mb-4 opacity-30">◉</div>
              <p className="text-sm text-fg-dim max-w-md">
                Ask about market intelligence, regulatory changes, portfolio impacts,
                or specific companies. The copilot answers from ingested evidence only.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-3 max-w-lg">
                {[
                  "What is the impact of RBI's latest policy on banking stocks?",
                  "How will the new SEBI circular affect my portfolio?",
                  "Recent regulatory changes in Indian markets",
                  "What sectors are benefiting from the current budget?",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInput(q);
                    }}
                    className="text-xs text-left text-fg-dim bg-surface-alt border border-surface-border rounded-lg p-3 hover:bg-surface-hover hover:text-fg transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] ${
                  msg.role === "user"
                    ? "bg-accent-blue-bg border border-accent-blue-border rounded-2xl rounded-br-lg px-4 py-3"
                    : "card p-4"
                }`}
              >
                {msg.role === "assistant" ? (
                  <div className="space-y-3">
                    {msg.abstained && (
                      <div className="flex items-center gap-2 text-accent-amber text-xs mb-2">
                        <span className="badge-amber">ABSTAINED</span>
                        <span>{msg.abstention_reason}</span>
                      </div>
                    )}

                    <div className="text-sm text-fg leading-relaxed space-y-2">
                      {renderMessageContent(msg.content)}
                    </div>

                    {msg.verified_facts && msg.verified_facts.length > 0 && (
                      <div className="fact-box">
                        <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                          Verified Facts
                        </p>
                        <ul className="space-y-1">
                          {msg.verified_facts.map((fact, i) => (
                            <li key={i} className="text-xs text-fg-muted flex items-start gap-2">
                              <span className="text-accent-green mt-0.5">✓</span>
                              {fact}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {msg.analysis && (
                      <div className="analysis-box">
                        <p className="text-2xs text-accent-blue uppercase tracking-wider mb-1">
                          ANALYSIS
                        </p>
                        <p className="text-xs text-fg-muted">{msg.analysis}</p>
                      </div>
                    )}

                    {msg.portfolio_relevance && (
                      <div className="bg-accent-green-bg border border-accent-green-border rounded-lg p-3">
                        <p className="text-2xs text-accent-green uppercase tracking-wider mb-1">
                          PORTFOLIO RELEVANCE
                        </p>
                        <p className="text-xs text-fg-muted">{msg.portfolio_relevance}</p>
                      </div>
                    )}

                    {msg.uncertainty && (
                      <div className="bg-accent-amber-bg border border-accent-amber-border rounded-lg p-3">
                        <p className="text-2xs text-accent-amber uppercase tracking-wider mb-1">
                          UNCERTAINTY
                        </p>
                        <p className="text-xs text-fg-muted">{msg.uncertainty}</p>
                      </div>
                    )}

                    {msg.sources && msg.sources.length > 0 && (
                      <div>
                        <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                          Sources ({msg.sources.length})
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {msg.sources.map((src, i) => (
                            <button
                              key={i}
                              onClick={() => setSelectedSource(src)}
                              className="text-2xs bg-surface-alt border border-surface-border rounded px-2 py-1 text-fg-dim hover:text-fg hover:border-surface-border-light transition-colors"
                            >
                              {src.source_name}: {src.title.length > 30 ? src.title.slice(0, 28) + "…" : src.title}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-fg">{msg.content}</p>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="card p-4">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-accent-blue rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-accent-blue rounded-full animate-bounce" style={{ animationDelay: "0.1s" }} />
                  <div className="w-2 h-2 bg-accent-blue rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-surface-border">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === "portfolio_impact"
                  ? "Ask about your portfolio impact..."
                  : "Ask about market intelligence..."
              }
              className="flex-1 bg-surface-alt border border-surface-border rounded-xl px-4 py-3 text-sm text-fg placeholder:text-fg-dim focus:outline-none focus:ring-2 focus:ring-accent-blue"
              disabled={loading}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="btn-primary rounded-xl px-5 py-3 disabled:opacity-40"
            >
              Send
            </button>
          </div>
          <p className="text-2xs text-fg-faint mt-2">
            Responses are generated from ingested evidence only. The copilot never invents citations.
          </p>
        </div>
      </div>

      {/* Evidence panel / sidebar */}
      {hasSources && (
        <div className="w-80 border-l border-surface-border bg-surface-alt overflow-y-auto shrink-0 hidden lg:block">
          <div className="px-4 py-3 border-b border-surface-border">
            <p className="text-xs font-medium text-fg">Cited Evidence</p>
          </div>
          <div className="p-3 space-y-2">
            {messages
              .filter((m) => m.role === "assistant" && m.sources)
              .flatMap((m) => m.sources || [])
              .map((src, i) => (
                <button
                  key={i}
                  onClick={() => setSelectedSource(src)}
                  className={`w-full text-left card p-3 transition-colors hover:bg-surface-hover ${
                    selectedSource?.evidence_id === src.evidence_id
                      ? "border-accent-blue"
                      : ""
                  }`}
                >
                  <p className="text-xs font-medium text-fg truncate">{src.title}</p>
                  <p className="text-2xs text-fg-dim mt-1">{src.source_name}</p>
                  {src.similarity && (
                    <div className="mt-1.5">
                      <ConfidenceBar label="Relevance" value={src.similarity} />
                    </div>
                  )}
                  <p className="text-2xs text-fg-dim mt-1.5 line-clamp-2">{src.snippet}</p>
                </button>
              ))}
          </div>
        </div>
      )}

      {/* Source detail modal */}
      {selectedSource && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50"
          onClick={() => setSelectedSource(null)}
        >
          <div
            className="card max-w-xl w-full max-h-[70vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="text-sm font-semibold text-fg truncate">
                {selectedSource.title}
              </h3>
              <button
                onClick={() => setSelectedSource(null)}
                className="text-fg-dim hover:text-fg text-lg leading-none"
              >
                ✕
              </button>
            </div>
            <div className="card-body space-y-3">
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-2xs text-fg-dim">Source</p>
                  <p className="text-fg">{selectedSource.source_name}</p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Evidence ID</p>
                  <p className="font-mono text-fg-muted">{selectedSource.evidence_id}</p>
                </div>
                {selectedSource.similarity && (
                  <div>
                    <p className="text-2xs text-fg-dim">Relevance</p>
                    <span className="font-mono text-fg">
                      {Math.round(selectedSource.similarity * 100)}%
                    </span>
                  </div>
                )}
                {selectedSource.url && (
                  <div>
                    <p className="text-2xs text-fg-dim">URL</p>
                    <a
                      href={selectedSource.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent-blue hover:underline"
                    >
                      Open
                    </a>
                  </div>
                )}
              </div>
              <div>
                <p className="text-2xs text-fg-dim uppercase tracking-wider mb-1">Snippet</p>
                <p className="text-xs text-fg-muted bg-surface-alt rounded-lg p-3">
                  {selectedSource.snippet}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Conversation history panel */}
      {showConversations && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-start justify-end"
          onClick={() => setShowConversations(false)}
        >
          <div
            className="w-96 h-full bg-surface border-l border-surface-border overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-surface-border flex items-center justify-between">
              <h2 className="text-sm font-semibold text-fg">Conversations</h2>
              <button
                onClick={() => setShowConversations(false)}
                className="text-fg-dim hover:text-fg"
              >
                ✕
              </button>
            </div>
            <div className="p-3 space-y-1">
              {conversations.length === 0 ? (
                <p className="text-xs text-fg-dim p-4 text-center">No conversations yet</p>
              ) : (
                conversations.map((conv) => (
                  <button
                    key={conv.id}
                    onClick={() => loadConversation(conv.id)}
                    className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${
                      conv.id === conversationId
                        ? "bg-surface-hover"
                        : "hover:bg-surface-alt"
                    }`}
                  >
                    <p className="text-sm font-medium text-fg truncate">{conv.title}</p>
                    <p className="text-2xs text-fg-dim mt-0.5">
                      {conv.mode === "portfolio_impact" ? "Portfolio" : "Market Intel"} · {conv.message_count} messages
                    </p>
                  </button>
                ))
              )}
              <button
                onClick={() => {
                  setConversationId(null);
                  setMessages([]);
                  setShowConversations(false);
                }}
                className="w-full text-left px-4 py-3 rounded-lg text-sm text-accent-blue hover:bg-surface-hover transition-colors"
              >
                + New Conversation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
