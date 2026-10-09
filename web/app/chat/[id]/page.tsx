'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { conversationApi, Message } from '../../../lib/api';
import { useStream } from '../../../hooks/useStream';
import { MessageBubble } from '../../../components/chat/MessageBubble';
import { Composer } from '../../../components/chat/Composer';
import { useAuth } from '../../../hooks/useAuth';
import { formatCurrency } from '../../../lib/format';
import { Zap, ShieldCheck } from 'lucide-react';

export default function ConversationPage() {
  const params = useParams();
  const id = params?.id as string;

  const { refreshStats } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    isStreaming,
    streamingText,
    currentMeta,
    currentDone,
    sendPrompt,
    stopStreaming,
  } = useStream();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadMessages = useCallback(async () => {
    if (!id) return;
    try {
      const msgs = await conversationApi.getMessages(id);
      setMessages(Array.isArray(msgs) ? msgs : []);
    } catch (e) {
      console.error('Failed to load messages', e);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText]);

  // Handle pending prompt from new conversation creation
  useEffect(() => {
    if (!id || loading) return;
    const pendingKey = `pending_prompt_${id}`;
    const pendingPrompt = sessionStorage.getItem(pendingKey);
    if (pendingPrompt) {
      sessionStorage.removeItem(pendingKey);
      handleSendPrompt(pendingPrompt);
    }
  }, [id, loading]);

  const handleSendPrompt = async (promptText: string) => {
    const userMsg: Message = {
      id: `temp_user_${Date.now()}`,
      conversation_id: id,
      sender: 'user',
      content: promptText,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);

    let currentReqId: string | null = null;

    await sendPrompt(promptText, id, {
      onMeta: (meta) => {
        currentReqId = meta.request_id;
      },
      onDone: (done) => {
        refreshStats();
      },
      onVerificationUpdate: (verEvent) => {
        // Update specific request message status in real time
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.request_id === verEvent.status || msg.request_id === currentReqId) {
              return {
                ...msg,
                verification_status: verEvent.status,
                net_saved: verEvent.net_saved ?? msg.net_saved,
              };
            }
            return msg;
          })
        );
        refreshStats();
      },
      onError: () => {
        loadMessages();
      },
    });

    await loadMessages();
  };

  const convSaved = messages.reduce((acc, m) => acc + (m.net_saved || 0), 0);

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Top Header with Chat Savings */}
      <header className="py-2.5 px-6 border-b border-zinc-800/60 bg-zinc-900/40 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-zinc-200">Conversation Session</span>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium">
            <span>Saved {formatCurrency(convSaved)} in this chat</span>
          </div>
        </div>
      </header>

      {/* Messages Scroll View */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="h-full flex items-center justify-center text-zinc-500 text-xs">
            Loading messages...
          </div>
        ) : messages.length === 0 && !isStreaming ? (
          <div className="h-full flex items-center justify-center text-zinc-500 text-xs">
            Start typing below to talk to LLM Router!
          </div>
        ) : (
          <div className="pb-8">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                sender={msg.sender}
                content={msg.content}
                model={msg.model_used}
                tier={msg.routing_tier}
                costUsd={msg.cost_usd}
                baselineCostUsd={msg.baseline_cost_usd}
                netSaved={msg.net_saved}
                verificationStatus={msg.verification_status}
              />
            ))}

            {/* Live Streaming Response Bubble */}
            {isStreaming && (
              <MessageBubble
                sender="assistant"
                content={streamingText}
                model={currentMeta?.model}
                tier={currentMeta?.tier}
                costUsd={currentDone?.answer_cost}
                baselineCostUsd={currentDone?.baseline_cost}
                netSaved={currentDone?.net_saved}
                isStreaming={true}
              />
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Composer Input */}
      <Composer
        onSend={handleSendPrompt}
        isStreaming={isStreaming}
        onStop={stopStreaming}
      />
    </div>
  );
}
