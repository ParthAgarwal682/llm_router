import React from 'react';
import { getTierColor, formatModelName, formatCurrency, formatPercent } from '../../lib/format';
import { Sparkles, ShieldCheck, Zap, Layers, AlertCircle } from 'lucide-react';

interface QualityBadgeProps {
  tier?: string;
  model?: string;
  answerCost?: number;
  baselineCost?: number;
  netSaved?: number;
  savedPercent?: number;
  verificationStatus?: string;
  isProvisional?: boolean;
}

export const QualityBadge: React.FC<QualityBadgeProps> = ({
  tier = 'simple',
  model,
  answerCost = 0,
  baselineCost = 0,
  netSaved = 0,
  savedPercent,
  verificationStatus,
  isProvisional = false,
}) => {
  const styles = getTierColor(tier);
  const calcPercent = baselineCost > 0 ? (netSaved / baselineCost) * 100 : (savedPercent ?? 0);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs my-1">
      {/* Tier Pill */}
      <span
        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border font-medium ${styles.bg} ${styles.text} ${styles.border}`}
      >
        <Sparkles className="w-3 h-3" />
        <span className="capitalize">{tier} Tier</span>
        <span className="opacity-70 text-[10px]">({formatModelName(model)})</span>
      </span>

      {/* Savings Pill */}
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border font-semibold ${
          netSaved >= 0
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
            : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
        }`}
      >
        <Zap className="w-3 h-3 fill-current" />
        <span>
          Saved {formatCurrency(netSaved)} ({calcPercent.toFixed(1)}%) vs GPT-4o
        </span>
        {isProvisional && (
          <span className="text-[10px] uppercase font-normal tracking-wider opacity-75">
            [Est.]
          </span>
        )}
      </span>

      {/* Verification Status Pill */}
      {verificationStatus && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-zinc-800/80 text-zinc-300 border border-zinc-700/60 text-[11px]">
          {verificationStatus === 'verifying' && (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
              <span>Verifying...</span>
            </>
          )}
          {verificationStatus === 'arbitrating' && (
            <>
              <Layers className="w-3 h-3 text-purple-400 animate-pulse" />
              <span>3-Critic Arbitration</span>
            </>
          )}
          {verificationStatus === 'passed' && (
            <>
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>Verified Correct</span>
            </>
          )}
          {verificationStatus === 'failed_escalated' && (
            <>
              <AlertCircle className="w-3 h-3 text-amber-400" />
              <span>Escalated to Strong LLM</span>
            </>
          )}
          {verificationStatus === 'complete' && (
            <>
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              <span>Finalized</span>
            </>
          )}
        </span>
      )}
    </div>
  );
};
