export interface User {
  id: string;
  email: string;
  daily_limit: number;
  requests_today: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: 'user' | 'assistant';
  content: string;
  model_used?: string;
  cost_usd?: number;
  baseline_cost_usd?: number;
  net_saved?: number;
  routing_tier?: string;
  verification_status?: string;
  request_id?: string;
  created_at: string;
}

export interface UserStats {
  total_requests: number;
  total_net_saved: number;
  total_baseline_cost: number;
  total_actual_cost: number;
  saved_percent: number;
  escalation_rate: number;
  daily_series: Array<{
    date: string;
    net_saved: number;
    actual_cost: number;
    baseline_cost: number;
  }>;
  by_model: Array<{
    model: string;
    count: number;
    total_cost: number;
  }>;
  by_tier: Array<{
    tier: string;
    count: number;
    total_cost: number;
  }>;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
  if (typeof window !== 'undefined') {
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }
};

export const getAccessToken = (): string | null => {
  if (!accessToken && typeof window !== 'undefined') {
    accessToken = localStorage.getItem('access_token');
  }
  return accessToken;
};

async function apiFetch<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // send cookies for refresh token
  };

  let res = await fetch(`${API_BASE}${endpoint}`, config);

  if (res.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/register')) {
    // Try refreshing token
    try {
      const refreshRes = await fetch(`${API_BASE}/v1/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (refreshRes.ok) {
        const data = await refreshRes.json();
        setAccessToken(data.access_token);
        headers.set('Authorization', `Bearer ${data.access_token}`);
        res = await fetch(`${API_BASE}${endpoint}`, { ...config, headers });
      } else {
        setAccessToken(null);
        if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
          window.location.href = '/login';
        }
      }
    } catch {
      setAccessToken(null);
    }
  }

  if (!res.ok) {
    let errMessage = 'An error occurred';
    try {
      const errData = await res.json();
      errMessage = errData.detail || errData.message || errMessage;
    } catch {}
    throw new Error(errMessage);
  }

  return res.json();
}

export const authApi = {
  register: async (email: string, password: string) => {
    const data = await apiFetch<{ user_id: string; email: string; access_token: string }>('/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    return data;
  },

  login: async (email: string, password: string) => {
    const data = await apiFetch<{ access_token: string; token_type: string }>('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    return data;
  },

  logout: async () => {
    try {
      await apiFetch('/v1/auth/logout', { method: 'POST' });
    } finally {
      setAccessToken(null);
    }
  },

  me: async (): Promise<User> => {
    return apiFetch<User>('/v1/auth/me');
  },
};

export const conversationApi = {
  list: async (page = 1, limit = 50): Promise<{ conversations: Conversation[]; total: number }> => {
    const data = await apiFetch<any>(`/v1/conversations?page=${page}&limit=${limit}`);
    if (Array.isArray(data)) {
      return { conversations: data, total: data.length };
    }
    return {
      conversations: Array.isArray(data?.conversations) ? data.conversations : [],
      total: data?.total ?? (Array.isArray(data?.conversations) ? data.conversations.length : 0),
    };
  },

  create: async (title?: string): Promise<Conversation> => {
    return apiFetch<Conversation>('/v1/conversations', {
      method: 'POST',
      body: JSON.stringify({ title: title || 'New Conversation' }),
    });
  },

  rename: async (id: string, title: string): Promise<Conversation> => {
    return apiFetch<Conversation>(`/v1/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },

  delete: async (id: string): Promise<{ status: string }> => {
    return apiFetch<{ status: string }>(`/v1/conversations/${id}`, {
      method: 'DELETE',
    });
  },

  getMessages: async (id: string): Promise<Message[]> => {
    const raw = await apiFetch<any[]>(`/v1/conversations/${id}/messages`);
    if (!Array.isArray(raw)) return [];

    const messages: Message[] = [];
    for (const item of raw) {
      // If already formatted as a standard Message object with sender and content
      if (item.sender && (item.content !== undefined || item.text !== undefined)) {
        messages.push({
          ...item,
          content: item.content ?? item.text ?? '',
        });
        continue;
      }

      // If backend returned a request row (prompt + response_text)
      if (item.prompt) {
        messages.push({
          id: `${item.id}_user`,
          conversation_id: item.conversation_id || id,
          sender: 'user',
          content: item.prompt,
          created_at: item.created_at,
          request_id: item.id,
        });
      }

      if (item.response_text !== undefined && item.response_text !== null) {
        messages.push({
          id: `${item.id}_assistant`,
          conversation_id: item.conversation_id || id,
          sender: 'assistant',
          content: item.response_text,
          model_used: item.model_used,
          routing_tier: item.tier || item.routing_tier,
          cost_usd: item.cost_usd,
          baseline_cost_usd: item.baseline_cost_usd,
          net_saved: item.net_saved,
          verification_status: item.verify_verdict || item.status || item.verification_status,
          request_id: item.id,
          created_at: item.created_at,
        });
      }
    }
    return messages;
  },
};

export const statsApi = {
  getStats: async (range: '7d' | '30d' | 'all' = '30d'): Promise<UserStats> => {
    return apiFetch<UserStats>(`/v1/me/stats?range=${range}`);
  },
};

export const requestApi = {
  get: async (requestId: string) => {
    return apiFetch<any>(`/v1/requests/${requestId}`);
  },
};
