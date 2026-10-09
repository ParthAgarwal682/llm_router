'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Composer } from '../../components/chat/Composer';
import { conversationApi } from '../../lib/api';
import { Sparkles, Zap, ShieldCheck, DollarSign } from 'lucide-react';

const SUGGESTIONS = [
  {
    title: 'Code Generation',
    prompt: 'Write a Python function to find the longest palindrome substring in a given string with comments.',
    tier: 'simple',
  },
  {
    title: 'Text Summarization',
    prompt: 'Summarize the key advantages of using asynchronous streaming endpoints in FastAPI.',
    tier: 'simple',
  },
  {
    title: 'Complex Reasoning',
    prompt: 'Compare microservices vs monolith architecture for an e-commerce platform processing 100k orders/day.',
    tier: 'moderate',
  },
  {
    title: 'Multi-Step Verification',
    prompt: 'Solve this riddle: I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?',
    tier: 'complex',
  },
];

export default function ChatPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);

  const handleSendPrompt = async (prompt: string) => {
    if (creating) return;
    setCreating(true);
    try {
      const conv = await conversationApi.create();
      // Store initial prompt in session storage to trigger stream on navigate
      sessionStorage.setItem(`pending_prompt_${conv.id}`, prompt);
      router.push(`/chat/${conv.id}`);
    } catch (e) {
      console.error('Failed to create conversation', e);
      setCreating(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950">
      {/* Top Banner Header */}
      <header className="py-3 px-6 border-b border-zinc-800/40 bg-zinc-900/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-zinc-200">LLM Router Engine v1.0</span>
        </div>
        <div className="text-xs text-zinc-400 flex items-center gap-4">
          <span className="flex items-center gap-1">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> Baseline: GPT-4o ($2.50 / $10.00 M)
          </span>
        </div>
      </header>

      {/* Main Empty State Content */}
      <div className="flex-1 overflow-y-auto flex flex-col items-center justify-center p-6 text-center max-w-3xl mx-auto space-y-8">
        <div className="space-y-3">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-zinc-950 shadow-xl shadow-emerald-950/80 mb-2">
            <Zap className="w-7 h-7 fill-current" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">
            What can I help you route today?
          </h1>
          <p className="text-sm text-zinc-400 max-w-lg mx-auto">
            Prompts are automatically classified as <span className="text-emerald-400 font-medium">Simple</span>, <span className="text-amber-400 font-medium">Moderate</span>, or <span className="text-purple-400 font-medium">Complex</span> to route to the cheapest model with automated background arbitration.
          </p>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full text-left">
          <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
            <div className="flex items-center gap-1.5 text-emerald-400 font-semibold text-xs">
              <DollarSign className="w-4 h-4" /> Max Dollar Savings
            </div>
            <p className="text-[11px] text-zinc-400 leading-normal">
              Uses Llama 3.1 8B for simple queries (98% cheaper than GPT-4o).
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
            <div className="flex items-center gap-1.5 text-amber-400 font-semibold text-xs">
              <ShieldCheck className="w-4 h-4" /> Single-Judge Verification
            </div>
            <p className="text-[11px] text-zinc-400 leading-normal">
              Background verification checks response quality against a strong model.
            </p>
          </div>
          <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-800/80 space-y-1">
            <div className="flex items-center gap-1.5 text-purple-400 font-semibold text-xs">
              <Sparkles className="w-4 h-4" /> 3-Critic Arbitration
            </div>
            <p className="text-[11px] text-zinc-400 leading-normal">
              LangGraph critics arbitrate disagreements before final answer delivery.
            </p>
          </div>
        </div>

        {/* Suggestion Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
          {SUGGESTIONS.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleSendPrompt(item.prompt)}
              className="p-3.5 rounded-xl bg-zinc-900/40 hover:bg-zinc-900 border border-zinc-800/60 hover:border-emerald-500/40 text-left transition-all group"
            >
              <div className="text-xs font-medium text-zinc-200 group-hover:text-emerald-400 transition-colors flex items-center justify-between mb-1">
                <span>{item.title}</span>
                <Sparkles className="w-3 h-3 text-zinc-600 group-hover:text-emerald-400 transition-colors" />
              </div>
              <p className="text-[11px] text-zinc-500 line-clamp-2">{item.prompt}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Composer */}
      <Composer onSend={handleSendPrompt} isStreaming={creating} disabled={creating} />
    </div>
  );
}
