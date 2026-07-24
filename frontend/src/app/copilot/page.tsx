"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchApi, getConversations, chatSend, type Conversation, type ChatMessage } from "@/lib/api";
import PageHeader from "../components/PageHeader";
import LiveIndicator from "../components/LiveIndicator";

export default function CopilotPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const chatEnd = useRef<HTMLDivElement>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchConversations = useCallback(async () => {
    try {
      setConversations(await getConversations());
    } catch (e: any) {
      setError(e.message || "Failed to load conversations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setError(null);
    const userMsg: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    try {
      const res = await chatSend(activeConv, text);
      setActiveConv(res.conversation_id);
      setMessages((prev) => [...prev, { role: "assistant", content: res.response }]);
      fetchConversations();
    } catch (e: any) {
      setError(e.message || "Failed to send message");
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="page-container">
      {!apiUrl && (
        <div className="mb-4 px-4 py-3 bg-accent-amber-bg border border-accent-amber-border rounded-lg text-sm text-accent-amber text-center">
          ⚠ NEXT_PUBLIC_API_URL is not configured. Using fallback http://localhost:8000
        </div>
      )}

      <PageHeader title="Copilot" subtitle="AI-powered financial intelligence assistant"
        actions={<LiveIndicator />}
      />

      {error && (
        <div className="mb-4 card p-4 border-l-2 border-l-accent-red">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-accent-red">Error</p>
              <p className="text-xs text-fg-muted mt-1">{error}</p>
            </div>
            <button onClick={() => setError(null)} className="btn-ghost text-xs shrink-0">Dismiss</button>
          </div>
        </div>
      )}

      <div className="flex gap-4 h-[calc(100vh-12rem)]">
        <div className="w-64 shrink-0 space-y-2 overflow-y-auto">
          <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Conversations</p>
          {loading ? (
            [1,2,3].map((i) => <div key={i} className="card p-3 animate-pulse"><div className="h-3 bg-surface-hover rounded w-3/4" /></div>)
          ) : conversations.length === 0 ? (
            <div className="card p-3 text-center text-2xs text-fg-dim">No conversations yet</div>
          ) : (
            conversations.map((conv) => (
              <div key={conv.id} className={`card p-3 cursor-pointer hover:bg-surface-hover transition-colors ${activeConv === conv.id ? "ring-1 ring-accent-blue" : ""}`}
                onClick={() => setActiveConv(conv.id)}>
                <p className="text-xs text-fg truncate">{conv.title || "Untitled"}</p>
                <p className="text-2xs text-fg-dim mt-1">{new Date(conv.updated_at || conv.created_at).toLocaleDateString()}</p>
              </div>
            ))
          )}
        </div>

        <div className="flex-1 card flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <div className="text-center text-fg-dim">
                  <p className="text-lg mb-1">✦</p>
                  <p className="text-sm">Ask anything about financial intelligence</p>
                  <p className="text-2xs mt-2">e.g. "What's the impact of RBI rate decision?"</p>
                </div>
              </div>
            )}
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[70%] rounded-lg p-3 text-sm ${msg.role === "user" ? "bg-accent-blue-bg border border-accent-blue-border text-fg" : "bg-surface-alt text-fg-muted"}`}>
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="bg-surface-alt rounded-lg p-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEnd} />
          </div>
          <div className="border-t border-surface-border p-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder="Ask about markets, events, impacts..."
                className="flex-1"
                disabled={sending}
              />
              <button onClick={handleSend} disabled={sending || !input.trim()} className="btn-primary">Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
