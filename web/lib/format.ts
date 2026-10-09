export function formatCurrency(amount: number | null | undefined, precision = 4): string {
  if (amount === null || amount === undefined || isNaN(amount)) return '$0.0000';
  const isNegative = amount < 0;
  const absAmount = Math.abs(amount);
  
  if (absAmount >= 1) {
    return (isNegative ? '-$' : '$') + absAmount.toFixed(2);
  }
  if (absAmount >= 0.01) {
    return (isNegative ? '-$' : '$') + absAmount.toFixed(3);
  }
  return (isNegative ? '-$' : '$') + absAmount.toFixed(precision);
}

export function formatPercent(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return '0%';
  return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`;
}

export function formatModelName(model: string | undefined): string {
  if (!model) return 'LLM Router';
  if (model.includes('gpt-4o') || model === 'gpt4o') return 'GPT-4o';
  if (model.includes('mini') || model === 'gpt4o_mini') return 'GPT-4o mini';
  if (model.includes('llama-3.1-8b') || model === 'llama_8b') return 'Llama 3.1 8B';
  if (model.includes('llama-3.3-70b') || model === 'llama_70b') return 'Llama 3.3 70B';
  if (model.includes('claude-3-5-sonnet') || model === 'claude_sonnet') return 'Claude 3.5 Sonnet';
  if (model.includes('gemini-2.0-flash') || model === 'gemini_flash') return 'Gemini 2.0 Flash';
  return model;
}

export function getTierColor(tier?: string): { bg: string; text: string; border: string } {
  switch (tier?.toLowerCase()) {
    case 'simple':
      return { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' };
    case 'moderate':
      return { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' };
    case 'complex':
      return { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20' };
    default:
      return { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20' };
  }
}
