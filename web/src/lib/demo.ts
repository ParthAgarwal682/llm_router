import type { Conversation, Message, UserStats } from "./api"

export const demoConversations: Conversation[] = [
  {
    id: "demo-1",
    title: "A better way to build APIs",
    user_id: "demo",
    created_at: "2026-10-08",
    updated_at: "2026-10-08",
  },
  {
    id: "demo-2",
    title: "Making sense of vector databases",
    user_id: "demo",
    created_at: "2026-10-08",
    updated_at: "2026-10-08",
  },
  {
    id: "demo-3",
    title: "Ideas for a weekend project",
    user_id: "demo",
    created_at: "2026-10-07",
    updated_at: "2026-10-07",
  },
  {
    id: "demo-4",
    title: "Explain async / await",
    user_id: "demo",
    created_at: "2026-10-07",
    updated_at: "2026-10-07",
  },
  {
    id: "demo-5",
    title: "A little help with my SQL query",
    user_id: "demo",
    created_at: "2026-10-06",
    updated_at: "2026-10-06",
  },
]
export const demoStats: UserStats = {
  total_requests: 142,
  total_net_saved: 1.4582,
  total_baseline_cost: 1.542,
  total_actual_cost: 0.0838,
  saved_percent: 94.5,
  escalation_rate: 0.04,
  daily_series: Array.from({ length: 14 }, (_, i) => {
    const baseline_cost = [
      0.07, 0.12, 0.08, 0.11, 0.065, 0.13, 0.09, 0.14, 0.1, 0.08, 0.145, 0.11,
      0.16, 0.13,
    ][i]
    return {
      date: `2026-10-${String(i + 1).padStart(2, "0")}`,
      net_saved: baseline_cost * 0.945,
      actual_cost: baseline_cost * 0.055,
      baseline_cost,
    }
  }),
  by_model: [
    { model: "llama_8b", count: 89, total_cost: 0.018 },
    { model: "gpt_4o_mini", count: 31, total_cost: 0.025 },
    { model: "llama_70b", count: 22, total_cost: 0.0408 },
  ],
  by_tier: [
    { tier: "simple", count: 89 },
    { tier: "moderate", count: 31 },
    { tier: "complex", count: 22 },
  ],
}
export const modelName = (model?: string) => {
  if (!model) return "Auto-selected model"
  if (model.includes("70b")) return "Llama 3.3 70B"
  if (model.includes("8b")) return "Llama 3.1 8B"
  if (model.includes("mini")) return "GPT-4o Mini"
  return model
}
export function demoReply(prompt: string): string {
  if (/async|api|python|code/i.test(prompt))
    return `## A simpler way to build\n\nStart with a small, focused API and let it grow with your needs. **Clear boundaries beat clever abstractions.**\n\n1. Define the resources and the data each endpoint accepts.\n2. Validate inputs at the boundary.\n3. Keep your business logic separate from your HTTP handlers.\n4. Add consistent error responses and tests.\n\nFor example, a minimal FastAPI endpoint:\n\n\`\`\`python\nfrom fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/health")\nasync def health():\n    return {"status": "ok"}\n\`\`\`\n\n**The takeaway:** build the smallest useful version first, then add complexity only when you need it.\n\n*This is a sample response in the preview workspace. Sign in to send your prompt to a real model.*`
  if (/quantum/i.test(prompt))
    return `## Quantum computing, without the jargon\n\nA regular computer uses **bits**, which are either 0 or 1. A quantum computer uses **qubits**, which can exist in a combination of both until measured.\n\nThink of a coin: a classical bit is a coin lying heads or tails. A qubit is more like a spinning coin—but that analogy only goes so far.\n\nQuantum algorithms use **interference** to amplify useful results and cancel out less useful ones. This makes them promising for specific problems, such as simulating molecules—not automatically faster at everything.\n\n*This is a sample preview response. Sign in for live model routing.*`
  return `## A good place to start\n\nThe best ideas start with a clear question and a small first step. Here's a practical way to approach yours:\n\n- **Define the goal.** What would a useful outcome look like?\n- **Break it down.** Pick one manageable piece to work on first.\n- **Explore the options.** Compare the simplest approach with one alternative.\n- **Iterate.** Try it, learn from the result, and adjust.\n\n| Approach | Best for |\n| --- | --- |\n| Start small | Learning quickly |\n| Make a plan | Coordinating complex work |\n| Build a prototype | Testing an idea |\n\n*You're exploring a sample response in preview mode. Sign in to connect this question to the intelligent router.*`
}
export function demoHistory(conversation: Conversation): Message[] {
  return [
    {
      id: `${conversation.id}-u`,
      conversation_id: conversation.id,
      sender: "user",
      content: conversation.title,
      created_at: conversation.created_at,
    },
    {
      id: `${conversation.id}-a`,
      conversation_id: conversation.id,
      sender: "assistant",
      content: demoReply(conversation.title),
      model_used: "llama_8b",
      routing_tier: "simple",
      net_saved: 0.00197,
      baseline_cost_usd: 0.002,
      cost_usd: 0.00003,
      verification_status: "verified",
      created_at: conversation.created_at,
    },
  ]
}
