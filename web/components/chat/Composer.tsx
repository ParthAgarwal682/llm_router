import React, { useState, useRef, useEffect } from 'react';
import { Send, Square, Sparkles } from 'lucide-react';

interface ComposerProps {
  onSend: (prompt: string) => void;
  isStreaming: boolean;
  onStop?: () => void;
  disabled?: boolean;
}

export const Composer: React.FC<ComposerProps> = ({
  onSend,
  isStreaming,
  onStop,
  disabled = false,
}) => {
  const [prompt, setPrompt] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [prompt]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!prompt.trim() || isStreaming || disabled) return;
    onSend(prompt.trim());
    setPrompt('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="p-4 bg-gradient-to-t from-zinc-950 via-zinc-950/90 to-transparent">
      <div className="max-w-4xl mx-auto">
        <form
          onSubmit={handleSubmit}
          className="relative bg-zinc-900/90 border border-zinc-700/60 rounded-2xl shadow-2xl focus-within:border-emerald-500/60 focus-within:ring-1 focus-within:ring-emerald-500/30 transition-all overflow-hidden"
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything... Router will pick the cheapest optimal model!"
            disabled={disabled}
            className="w-full py-3.5 pl-4 pr-14 bg-transparent text-zinc-100 placeholder-zinc-500 text-sm focus:outline-none resize-none max-h-48 overflow-y-auto"
          />

          <div className="absolute right-2.5 bottom-2.5 flex items-center gap-2">
            {isStreaming ? (
              <button
                type="button"
                onClick={onStop}
                className="p-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-200 transition-colors"
                title="Stop response"
              >
                <Square className="w-4 h-4 fill-current text-rose-400" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!prompt.trim() || disabled}
                className="p-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:hover:bg-emerald-600 text-white transition-all shadow-md shadow-emerald-950"
                title="Send message"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>
        </form>

        <div className="flex items-center justify-between mt-2 px-2 text-[11px] text-zinc-500">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-emerald-400" />
            <span>Automatic cost arbitration enabled</span>
          </div>
          <span>Shift + Enter for new line</span>
        </div>
      </div>
    </div>
  );
};
