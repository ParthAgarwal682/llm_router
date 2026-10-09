import { useState, useCallback, useRef } from 'react';
import { getAccessToken } from '../lib/api';

export interface StreamMeta {
  model: string;
  tier: string;
  conversation_id: string;
  request_id: string;
}

export interface StreamDone {
  answer_cost: number;
  baseline_cost: number;
  net_saved: number;
  provisional: boolean;
  request_id: string;
}

export interface VerificationEvent {
  status: string;
  verdict?: string;
  net_saved?: number;
  verification_cost?: number;
  savings_final?: boolean;
}

interface UseStreamOptions {
  onMeta?: (meta: StreamMeta) => void;
  onToken?: (token: string) => void;
  onDone?: (done: StreamDone) => void;
  onError?: (error: string) => void;
  onVerificationUpdate?: (event: VerificationEvent) => void;
}

export function useStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [currentMeta, setCurrentMeta] = useState<StreamMeta | null>(null);
  const [currentDone, setCurrentDone] = useState<StreamDone | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startVerificationListener = useCallback((requestId: string, onUpdate?: (event: VerificationEvent) => void) => {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const token = getAccessToken();
    
    const eventSource = new EventSource(`${API_BASE}/v1/requests/${requestId}/events?token=${token || ''}`);

    const handleEvent = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (onUpdate) onUpdate(data);
        if (data.savings_final) {
          eventSource.close();
        }
      } catch (err) {
        console.error('Error parsing SSE event', err);
      }
    };

    eventSource.addEventListener('status', handleEvent);
    eventSource.addEventListener('final', handleEvent);
    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, []);

  const sendPrompt = useCallback(
    async (
      prompt: string,
      conversationId?: string,
      options: UseStreamOptions = {}
    ) => {
      setIsStreaming(true);
      setStreamingText('');
      setCurrentMeta(null);
      setCurrentDone(null);
      setError(null);

      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = getAccessToken();

      abortControllerRef.current = new AbortController();

      try {
        const response = await fetch(`${API_BASE}/v1/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            prompt,
            conversation_id: conversationId,
          }),
          signal: abortControllerRef.current.signal,
          credentials: 'include',
        });

        if (!response.ok) {
          const errJson = await response.json().catch(() => null);
          throw new Error(errJson?.detail || 'Failed to stream response');
        }

        if (!response.body) {
          throw new Error('No response body returned');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let accumulatedText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let currentEvent = 'message';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            if (trimmed.startsWith('event:')) {
              currentEvent = trimmed.substring(6).trim();
            } else if (trimmed.startsWith('data:')) {
              const dataStr = trimmed.substring(5).trim();
              try {
                const data = JSON.parse(dataStr);

                if (currentEvent === 'meta') {
                  setCurrentMeta(data);
                  options.onMeta?.(data);
                } else if (currentEvent === 'token') {
                  const delta = data.delta || '';
                  accumulatedText += delta;
                  setStreamingText(accumulatedText);
                  options.onToken?.(delta);
                } else if (currentEvent === 'done') {
                  setCurrentDone(data);
                  options.onDone?.(data);
                  if (data.request_id && options.onVerificationUpdate) {
                    startVerificationListener(data.request_id, options.onVerificationUpdate);
                  }
                } else if (currentEvent === 'error') {
                  throw new Error(data.message || 'Stream error');
                }
              } catch (e: any) {
                if (e.message !== 'Unexpected end of JSON input') {
                  console.error('SSE JSON parse error:', e, dataStr);
                }
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          const msg = err.message || 'An error occurred during streaming';
          setError(msg);
          options.onError?.(msg);
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [startVerificationListener]
  );

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  }, []);

  return {
    isStreaming,
    streamingText,
    currentMeta,
    currentDone,
    error,
    sendPrompt,
    stopStreaming,
    startVerificationListener,
  };
}
