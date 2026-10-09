'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { Conversation, conversationApi } from '../../lib/api';
import { useAuth } from '../../hooks/useAuth';
import { formatCurrency, formatPercent } from '../../lib/format';
import {
  Plus,
  MessageSquare,
  BarChart3,
  LogOut,
  Trash2,
  Edit2,
  Check,
  X,
  Zap,
  Sparkles,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';

interface SidebarProps {
  conversations: Conversation[];
  activeId?: string;
  onRefreshConversations: () => void;
  onSelectConversation?: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  conversations = [],
  activeId,
  onRefreshConversations,
  onSelectConversation,
}) => {
  const { user, stats, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const handleCreateNew = async () => {
    try {
      const newConv = await conversationApi.create();
      onRefreshConversations();
      if (onSelectConversation) {
        onSelectConversation(newConv.id);
      } else {
        router.push(`/chat/${newConv.id}`);
      }
    } catch (e) {
      console.error('Error creating conversation', e);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this chat?')) return;
    try {
      await conversationApi.delete(id);
      onRefreshConversations();
      if (activeId === id) {
        router.push('/chat');
      }
    } catch (e) {
      console.error('Error deleting conversation', e);
    }
  };

  const handleStartRename = (conv: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(conv.id);
    setEditTitle(conv.title);
  };

  const handleSaveRename = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!editTitle.trim()) return;
    try {
      await conversationApi.rename(id, editTitle.trim());
      setEditingId(null);
      onRefreshConversations();
    } catch (e) {
      console.error('Error renaming conversation', e);
    }
  };

  const totalSaved = stats?.total_net_saved ?? 0;
  const savedPercent = stats?.saved_percent ?? 0;

  return (
    <aside className="w-72 bg-zinc-950 border-r border-zinc-800/60 flex flex-col h-full shrink-0 select-none">
      {/* Header & Logo */}
      <div className="p-4 border-b border-zinc-800/60 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-950">
            <Zap className="w-4 h-4 text-zinc-950 fill-current" />
          </div>
          <div>
            <h1 className="font-bold text-sm text-zinc-100 leading-tight">LLM Router</h1>
            <p className="text-[10px] text-emerald-400 font-medium tracking-wide">
              Arbitrated Savings Engine
            </p>
          </div>
        </div>
      </div>

      {/* Total Savings Card */}
      <div className="p-3">
        <Link
          href="/usage"
          className="block p-3 rounded-xl bg-gradient-to-br from-emerald-950/40 via-zinc-900 to-zinc-900 border border-emerald-500/20 hover:border-emerald-500/40 transition-all group shadow-sm"
        >
          <div className="flex items-center justify-between text-xs text-zinc-400 mb-1">
            <span className="flex items-center gap-1 font-medium text-emerald-400">
              <Sparkles className="w-3.5 h-3.5" /> Lifetime Savings
            </span>
            <ChevronRight className="w-3.5 h-3.5 text-zinc-500 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xl font-extrabold text-zinc-50 tracking-tight">
              {formatCurrency(totalSaved)}
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              {savedPercent.toFixed(1)}% vs GPT-4o
            </span>
          </div>
        </Link>
      </div>

      {/* New Chat Button */}
      <div className="px-3 pb-2">
        <button
          onClick={handleCreateNew}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-all shadow-md shadow-emerald-950/50 active:scale-[0.98]"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Navigation Links */}
      <div className="px-3 py-1 space-y-0.5 border-b border-zinc-800/40 pb-2">
        <Link
          href="/chat"
          className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
            pathname.startsWith('/chat')
              ? 'bg-zinc-800/80 text-zinc-100 font-semibold'
              : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
          }`}
        >
          <MessageSquare className="w-4 h-4 text-emerald-400" />
          <span>Chat Workspace</span>
        </Link>
        <Link
          href="/usage"
          className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
            pathname.startsWith('/usage')
              ? 'bg-zinc-800/80 text-zinc-100 font-semibold'
              : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
          }`}
        >
          <BarChart3 className="w-4 h-4 text-emerald-400" />
          <span>Savings & Analytics</span>
        </Link>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <div className="px-2 py-1 text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
          Recent Chats
        </div>

        {(conversations || []).length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-zinc-600 italic">
            No chats yet. Start a new conversation above!
          </div>
        ) : (
          (conversations || []).map((conv) => {
            const isActive = activeId === conv.id;
            const isEditing = editingId === conv.id;

            return (
              <div
                key={conv.id}
                onClick={() => {
                  if (onSelectConversation) {
                    onSelectConversation(conv.id);
                  } else {
                    router.push(`/chat/${conv.id}`);
                  }
                }}
                className={`group relative flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all ${
                  isActive
                    ? 'bg-zinc-800 text-zinc-100 font-medium shadow-sm'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-2 overflow-hidden flex-1 min-w-0 pr-2">
                  <MessageSquare className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-emerald-400' : 'text-zinc-500'}`} />

                  {isEditing ? (
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full bg-zinc-950 text-zinc-100 px-1.5 py-0.5 rounded border border-emerald-500 text-xs focus:outline-none"
                      autoFocus
                    />
                  ) : (
                    <span className="truncate">{conv.title}</span>
                  )}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  {isEditing ? (
                    <>
                      <button
                        onClick={(e) => handleSaveRename(conv.id, e)}
                        className="p-1 text-emerald-400 hover:text-emerald-300"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingId(null);
                        }}
                        className="p-1 text-zinc-500 hover:text-zinc-300"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </>
                  ) : (
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5">
                      <button
                        onClick={(e) => handleStartRename(conv, e)}
                        className="p-1 text-zinc-400 hover:text-zinc-200"
                        title="Rename"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(conv.id, e)}
                        className="p-1 text-zinc-400 hover:text-rose-400"
                        title="Delete"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* User Footer */}
      <div className="p-3 border-t border-zinc-800/60 bg-zinc-900/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 overflow-hidden pr-2">
            <div className="w-7 h-7 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs font-semibold text-zinc-200 shrink-0">
              {user?.email?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div className="overflow-hidden min-w-0">
              <p className="text-xs font-medium text-zinc-200 truncate">{user?.email}</p>
              <p className="text-[10px] text-zinc-500">
                Limit: {user?.requests_today ?? 0}/{user?.daily_limit ?? 100} / day
              </p>
            </div>
          </div>

          <button
            onClick={() => logout().then(() => router.push('/login'))}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-rose-400 hover:bg-zinc-800 transition-colors shrink-0"
            title="Sign out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
