export interface User {
  id: string
  email: string
  daily_limit: number
  requests_today: number
  created_at: string
}
export interface Conversation {
  id: string
  title: string
  user_id: string
  created_at: string
  updated_at: string
}
export interface Message {
  id: string
  conversation_id: string
  sender: "user" | "assistant"
  content: string
  model_used?: string
  routing_tier?: string
  cost_usd?: number
  baseline_cost_usd?: number
  net_saved?: number
  verification_status?: string
  request_id?: string
  created_at: string
}
export interface UserStats {
  total_requests: number
  total_net_saved: number
  total_baseline_cost: number
  total_actual_cost: number
  saved_percent: number
  escalation_rate: number
  daily_series: Array<{
    date: string
    net_saved: number
    actual_cost: number
    baseline_cost: number
  }>
  by_model: Array<{
    model: string
    count: number
    total_cost: number
  }>
  by_tier: Array<{
    tier: string
    count: number
  }>
}

let accessToken = ""
let refreshPromise: Promise<boolean> | null = null
export const getBaseUrl = () =>
  localStorage.getItem("relay-api-url") ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://localhost:8000"
export const setBaseUrl = (url: string) =>
  localStorage.setItem("relay-api-url", url.replace(/\/$/, ""))

async function refresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${getBaseUrl()}/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) return false
        accessToken = (await response.json()).access_token
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

async function request(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers)
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`)
  if (options.body) headers.set("Content-Type", "application/json")
  let response: Response
  try {
    response = await fetch(`${getBaseUrl()}${path}`, {
      ...options,
      headers,
      credentials: "include",
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new Error(
      "Cannot reach the backend. Check your API URL and allow this preview origin in backend CORS settings.",
    )
  }
  if (
    response.status === 401 &&
    retry &&
    !path.startsWith("/v1/auth/") &&
    (await refresh())
  ) {
    return request(path, options, false)
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Please try again.`,
    )
  }
  return response
}
async function json<T>(path: string, options?: RequestInit): Promise<T> {
  return (await request(path, options)).json()
}

export const api = {
  async restore() {
    return (await refresh()) ? json<User>("/v1/auth/me") : null
  },
  async authenticate(email: string, password: string, register: boolean) {
    const result = await json<{ access_token: string }>(
      `/v1/auth/${register ? "register" : "login"}`,
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
    )
    accessToken = result.access_token
    return json<User>("/v1/auth/me")
  },
  async logout() {
    await request("/v1/auth/logout", { method: "POST" })
    accessToken = ""
  },
  async conversations(): Promise<Conversation[]> {
    const data = await json<Conversation[] | { conversations: Conversation[] }>(
      "/v1/conversations?limit=50",
    )
    return Array.isArray(data) ? data : data.conversations || []
  },
  create: (title: string) =>
    json<Conversation>("/v1/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  rename: (id: string, title: string) =>
    json<Conversation>(`/v1/conversations/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  remove: (id: string) =>
    request(`/v1/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  async messages(id: string): Promise<Message[]> {
    const data = await json<Array<Record<string, unknown>> | {
      messages: Array<Record<string, unknown>>
    }>(`/v1/conversations/${encodeURIComponent(id)}/messages`)
    const rows = Array.isArray(data) ? data : data.messages || []
    return rows.flatMap((row) => {
      const common = {
        conversation_id: id,
        created_at: String(row.created_at || ""),
      }
      const messages: Message[] = []
      if (row.prompt)
        messages.push({
          ...common,
          id: `${row.id}_user`,
          sender: "user",
          content: String(row.prompt),
        })
      if (row.response_text)
        messages.push({
          ...common,
          id: `${row.id}_assistant`,
          sender: "assistant",
          content: String(row.response_text),
          model_used: row.model_used as string,
          routing_tier: row.tier as string,
          cost_usd: row.cost_usd as number,
          baseline_cost_usd: row.baseline_cost_usd as number,
          net_saved: row.net_saved as number,
          verification_status: (row.verify_verdict || row.status) as string,
          request_id: String(row.id),
        })
      return messages
    })
  },
  stats: (range: string) => json<UserStats>(`/v1/me/stats?range=${range}`),
  async stream(
    prompt: string,
    conversationId: string | undefined,
    signal: AbortSignal,
    onEvent: EventCallback,
  ) {
    const response = await request("/v1/chat/stream", {
      method: "POST",
      body: JSON.stringify({ prompt, conversation_id: conversationId }),
      signal,
    })
    await readEvents(response, onEvent)
  },
  async verification(id: string, signal: AbortSignal, onEvent: EventCallback) {
    await readEvents(
      await request(`/v1/requests/${encodeURIComponent(id)}/events`, {
        signal,
      }),
      onEvent,
    )
  },
}
export type EventCallback = (
  event: string,
  data: Record<string, unknown>,
) => void
async function readEvents(response: Response, callback: EventCallback) {
  if (!response.body) throw new Error("Streaming is not available.")
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  const dispatch = (block: string) => {
    let event = "message"
    const data: string[] = []
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim()
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart())
    }
    if (data.length) {
      const text = data.join("\n")
      if (text !== "[DONE]") callback(event, JSON.parse(text))
    }
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      buffer = buffer.replace(/\r\n/g, "\n")
      let boundary
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        dispatch(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
      }
      if (done) {
        if (buffer.trim()) dispatch(buffer)
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
