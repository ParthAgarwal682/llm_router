'use client';

import React, { useEffect, useState } from 'react';
import { statsApi, UserStats } from '../../lib/api';
import { formatCurrency, formatPercent, formatModelName } from '../../lib/format';
import {
  DollarSign,
  TrendingUp,
  Zap,
  PieChart,
  ShieldAlert,
  ArrowLeft,
  Calendar,
  Sparkles,
  Layers,
} from 'lucide-react';
import Link from 'next/link';

export default function UsagePage() {
  const [range, setRange] = useState<'7d' | '30d' | 'all'>('30d');
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const s = await statsApi.getStats(range);
        setStats(s);
      } catch (e) {
        console.error('Failed to load stats', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [range]);

  return (
    <div className="flex-1 overflow-y-auto bg-zinc-950 p-6 sm:p-8 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800/60 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 mb-1">
            <Sparkles className="w-4 h-4" /> Lifetime Financial ROI
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Savings & Cost Analytics
          </h1>
          <p className="text-xs text-zinc-400 mt-1">
            Real-time dollar audit of actual LLM routing costs vs baseline GPT-4o expense
          </p>
        </div>

        {/* Range Selector */}
        <div className="flex items-center bg-zinc-900 border border-zinc-800 p-1 rounded-xl text-xs">
          {(['7d', '30d', 'all'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                range === r
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {r === '7d' ? 'Last 7 Days' : r === '30d' ? 'Last 30 Days' : 'All Time'}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center text-zinc-500 text-xs">Loading analytics...</div>
      ) : !stats ? (
        <div className="py-20 text-center text-zinc-500 text-xs">No usage data found yet.</div>
      ) : (
        <>
          {/* Key KPI Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Money Saved */}
            <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/50 via-zinc-900 to-zinc-900 border border-emerald-500/30 shadow-xl space-y-2">
              <div className="flex items-center justify-between text-xs text-emerald-400 font-semibold">
                <span>Net Dollar Saved</span>
                <DollarSign className="w-4 h-4" />
              </div>
              <div className="text-3xl font-black text-white tracking-tight">
                {formatCurrency(stats.total_net_saved)}
              </div>
              <div className="text-xs text-emerald-400 font-medium flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5" />
                <span>{stats.saved_percent.toFixed(1)}% saved vs GPT-4o</span>
              </div>
            </div>

            {/* Total Baseline Cost */}
            <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800/80 shadow-lg space-y-2">
              <div className="flex items-center justify-between text-xs text-zinc-400 font-medium">
                <span>Baseline (GPT-4o)</span>
                <Zap className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="text-2xl font-bold text-zinc-200">
                {formatCurrency(stats.total_baseline_cost)}
              </div>
              <div className="text-xs text-zinc-500">Hypothetical cost without router</div>
            </div>

            {/* Actual Spend */}
            <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800/80 shadow-lg space-y-2">
              <div className="flex items-center justify-between text-xs text-zinc-400 font-medium">
                <span>Actual Spend</span>
                <PieChart className="w-4 h-4 text-zinc-500" />
              </div>
              <div className="text-2xl font-bold text-emerald-400">
                {formatCurrency(stats.total_actual_cost)}
              </div>
              <div className="text-xs text-zinc-500">
                Across {stats.total_requests} requests
              </div>
            </div>

            {/* Escalation Rate */}
            <div className="p-5 rounded-2xl bg-zinc-900/80 border border-zinc-800/80 shadow-lg space-y-2">
              <div className="flex items-center justify-between text-xs text-zinc-400 font-medium">
                <span>Arbitration Rate</span>
                <ShieldAlert className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-2xl font-bold text-purple-400">
                {(stats.escalation_rate * 100).toFixed(1)}%
              </div>
              <div className="text-xs text-zinc-500">Escalated to multi-critic verification</div>
            </div>
          </div>

          {/* Breakdown Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* By Tier */}
            <div className="p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-4">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-400" /> Routing Tier Distribution
              </h3>
              <div className="space-y-3">
                {stats.by_tier.map((tier) => {
                  const percent = stats.total_requests > 0 ? (tier.count / stats.total_requests) * 100 : 0;
                  return (
                    <div key={tier.tier} className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="capitalize text-zinc-200">{tier.tier} Tier</span>
                        <span className="text-zinc-400">
                          {tier.count} requests ({percent.toFixed(1)}%) • {formatCurrency(tier.total_cost)}
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            tier.tier === 'simple'
                              ? 'bg-emerald-500'
                              : tier.tier === 'moderate'
                              ? 'bg-amber-500'
                              : 'bg-purple-500'
                          }`}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* By Model */}
            <div className="p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-4">
              <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                <PieChart className="w-4 h-4 text-emerald-400" /> Model Usage Breakdown
              </h3>
              <div className="space-y-3">
                {stats.by_model.map((m) => {
                  const percent = stats.total_requests > 0 ? (m.count / stats.total_requests) * 100 : 0;
                  return (
                    <div key={m.model} className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-zinc-200">{formatModelName(m.model)}</span>
                        <span className="text-zinc-400">
                          {m.count} calls ({percent.toFixed(1)}%) • {formatCurrency(m.total_cost)}
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-teal-500"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Daily Savings Time Series Table */}
          <div className="p-6 rounded-2xl bg-zinc-900/60 border border-zinc-800 space-y-4">
            <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-400" /> Daily Financial Audit Log
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400 font-semibold">
                    <th className="pb-3 px-2">Date</th>
                    <th className="pb-3 px-2">Baseline (GPT-4o)</th>
                    <th className="pb-3 px-2">Actual Spend</th>
                    <th className="pb-3 px-2">Net Saved</th>
                    <th className="pb-3 px-2">Savings %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/40">
                  {stats.daily_series.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-zinc-500 italic">
                        No activity recorded for this period yet.
                      </td>
                    </tr>
                  ) : (
                    stats.daily_series.map((day) => {
                      const dayPercent =
                        day.baseline_cost > 0
                          ? (day.net_saved / day.baseline_cost) * 100
                          : 0;
                      return (
                        <tr key={day.date} className="hover:bg-zinc-800/30 transition-colors">
                          <td className="py-3 px-2 font-mono text-zinc-300">{day.date}</td>
                          <td className="py-3 px-2 text-zinc-400">{formatCurrency(day.baseline_cost)}</td>
                          <td className="py-3 px-2 text-zinc-300">{formatCurrency(day.actual_cost)}</td>
                          <td className="py-3 px-2 font-semibold text-emerald-400">
                            {formatCurrency(day.net_saved)}
                          </td>
                          <td className="py-3 px-2">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-semibold border border-emerald-500/20">
                              {dayPercent.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
