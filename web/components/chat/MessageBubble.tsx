import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { QualityBadge } from './QualityBadge';
import { User, Bot, Copy, Check } from 'lucide-react';

interface MessageBubbleProps {
  sender: 'user' | 'assistant';
  content: string;
  model?: string;
  tier?: string;
  costUsd?: number;
  baselineCostUsd?: number;
  netSaved?: number;
  verificationStatus?: string;
  isStreaming?: boolean;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  sender,
  content,
  model,
  tier,
  costUsd,
  baselineCostUsd,
  netSaved,
  verificationStatus,
  isStreaming = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = sender === 'user';

  return (
    <div
      className={`group py-4 px-4 sm:px-6 transition-colors ${
        isUser ? 'bg-zinc-900/30' : 'bg-zinc-900/80 border-y border-zinc-800/40'
      }`}
    >
      <div className="max-w-4xl mx-auto flex gap-4">
        {/* Avatar */}
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
            isUser
              ? 'bg-zinc-700 text-zinc-200'
              : 'bg-gradient-to-tr from-emerald-600 to-teal-500 text-white shadow-md shadow-emerald-900/20'
          }`}
        >
          {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
        </div>

        {/* Content & Metadata */}
        <div className="flex-1 space-y-2 overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-xs text-zinc-400">
              {isUser ? 'You' : 'Router AI'}
            </span>
            {!isUser && !isStreaming && content && (
              <button
                onClick={handleCopy}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-zinc-200 text-xs flex items-center gap-1 p-1 rounded hover:bg-zinc-800"
                title="Copy response"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            )}
          </div>

          {!isUser && (model || tier || netSaved !== undefined) && (
            <QualityBadge
              tier={tier}
              model={model}
              answerCost={costUsd}
              baselineCost={baselineCostUsd}
              netSaved={netSaved}
              verificationStatus={verificationStatus}
            />
          )}

          {isUser ? (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words text-zinc-100">
              {content}
            </div>
          ) : (
            <div className="text-sm leading-relaxed space-y-2 break-words text-zinc-100">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                  strong: ({ children }) => <strong className="font-semibold text-zinc-50">{children}</strong>,
                  em: ({ children }) => <em className="italic text-zinc-200">{children}</em>,
                  ul: ({ children }) => <ul className="list-disc pl-5 my-2 space-y-1">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-5 my-2 space-y-1">{children}</ol>,
                  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                  h1: ({ children }) => <h1 className="text-lg font-bold text-zinc-100 mt-4 mb-2">{children}</h1>,
                  h2: ({ children }) => <h2 className="text-base font-bold text-zinc-100 mt-3 mb-1.5">{children}</h2>,
                  h3: ({ children }) => <h3 className="text-sm font-bold text-zinc-200 mt-2 mb-1">{children}</h3>,
                  code: ({ className, children, ...props }: any) => {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match && !String(children).includes('\n');
                    if (isInline) {
                      return (
                        <code className="bg-zinc-800 text-emerald-300 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
                          {children}
                        </code>
                      );
                    }
                    return (
                      <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 my-2 overflow-x-auto text-xs font-mono text-zinc-200">
                        <code className={className} {...props}>{children}</code>
                      </pre>
                    );
                  },
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-2 border-emerald-500 pl-3 my-2 italic text-zinc-400">
                      {children}
                    </blockquote>
                  ),
                }}
              >
                {content}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-2 h-4 ml-1 bg-emerald-400 animate-pulse align-middle" />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
