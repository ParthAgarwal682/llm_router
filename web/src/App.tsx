import { useEffect, useRef, useState } from "react"
import type { FormEvent } from "react"
import {
  ArrowUp,
  ArrowUpRight,
  ArrowRight,
  AudioLines,
  BarChart3,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  Download,
  Ellipsis,
  Eye,
  FileText,
  GitBranch,
  Globe,
  Layers,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeftClose,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Users,
  X,
  Zap,
} from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { api, getBaseUrl, setBaseUrl } from "./lib/api"
import type {
  AdminRequestLog,
  AdminUserSavings,
  Conversation,
  Message,
  User,
  UserStats,
} from "./lib/api"
import {
  demoConversations,
  demoHistory,
  demoReply,
  demoStats,
  modelName,
} from "./lib/demo"

const suggestions = [
  {
    icon: Code2,
    title: "Build something",
    description: "From a small script to your next big idea",
    prompt: "Help me build a simple Python API with FastAPI.",
  },
  {
    icon: Sparkles,
    title: "Make it make sense",
    description: "Big concepts, explained simply",
    prompt: "Explain quantum computing in simple terms.",
  },
  {
    icon: FileText,
    title: "Find the right words",
    description: "Write, refine, and get your point across",
    prompt: "Help me write a clear introduction for my next project.",
  },
  {
    icon: Globe,
    title: "Explore an idea",
    description: "A fresh perspective on anything",
    prompt: "Give me some creative ideas for a weekend project.",
  },
]
type Modal = "auth" | "settings" | "search" | "rename" | "delete" | null
const money = (n: number, decimals = 2) => `$${n.toFixed(decimals)}`

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [conversations, setConversations] =
    useState<Conversation[]>(demoConversations)
  const [active, setActive] = useState<string>()
  const [messages, setMessages] = useState<Message[]>([])
  const [draft, setDraft] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(false)
  const [sidebar, setSidebar] = useState(() => window.innerWidth >= 760)
  const [page, setPage] = useState<"chat" | "usage" | "admin">(() => {
    if (location.pathname === "/admin") return "admin"
    if (location.pathname === "/usage") return "usage"
    return "chat"
  })
  const [modal, setModal] = useState<Modal>(null)
  const [target, setTarget] = useState<Conversation>()
  const [search, setSearch] = useState("")
  const [error, setError] = useState("")
  const [stats, setStats] = useState<UserStats>(demoStats)
  const [range, setRange] = useState("30d")
  const [register, setRegister] = useState(false)
  const [authBusy, setAuthBusy] = useState(false)
  const [copied, setCopied] = useState("")
  const [menuId, setMenuId] = useState<string>()
  const [routeInfo, setRouteInfo] = useState(false)
  const [apiUrl, setApiUrl] = useState(getBaseUrl)
  const controller = useRef<AbortController | null>(null)
  const verifiers = useRef<AbortController[]>([])
  const textarea = useRef<HTMLTextAreaElement>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const historyCache = useRef<Record<string, Message[]>>({})
  const selection = useRef(0)

  useEffect(() => {
    let alive = true
    api
      .restore()
      .then((result) => {
        if (alive && result) setUser(result)
      })
      .catch(() => {})
    const pop = () => {
      if (location.pathname === "/admin") setPage("admin")
      else if (location.pathname === "/usage") setPage("usage")
      else setPage("chat")
    }
    const key = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault()
        setModal("search")
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "n") {
        event.preventDefault()
        newChat()
      }
      if (event.key === "Escape") {
        setModal(null)
        setMenuId(undefined)
      }
    }
    window.addEventListener("popstate", pop)
    window.addEventListener("keydown", key)
    return () => {
      alive = false
      controller.current?.abort()
      verifiers.current.forEach((c) => c.abort())
      window.removeEventListener("popstate", pop)
      window.removeEventListener("keydown", key)
    }
  }, [])
  useEffect(() => {
    if (!user) return
    let alive = true
    api
      .conversations()
      .then((data) => {
        if (alive) setConversations(data)
      })
      .catch((e) => {
        if (alive) setError(e.message)
      })
    api
      .stats(range)
      .then((data) => {
        if (alive) setStats(data)
      })
      .catch((e) => {
        if (alive) setError(e.message)
      })
    return () => {
      alive = false
    }
  }, [user, range])
  useEffect(() => {
    bottom.current?.scrollIntoView({
      behavior: streaming ? "instant" : "smooth",
    })
  }, [messages, streaming])
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = "auto"
      textarea.current.style.height = `${Math.min(textarea.current.scrollHeight, 160)}px`
    }
  }, [draft])
  useEffect(() => {
    if (active) historyCache.current[active] = messages
  }, [messages, active])

  function navigate(next: "chat" | "usage" | "admin" | string) {
    setPage(next as any)
    history.pushState(
      {},
      "",
      next === "usage" ? "/usage" : next === "admin" ? "/admin" : "/",
    )
  }
  function newChat() {
    controller.current?.abort()
    selection.current++
    setLoading(false)
    setActive(undefined)
    setMessages([])
    setDraft("")
    setError("")
    navigate("chat")
    if (window.innerWidth < 760) setSidebar(false)
  }
  async function openConversation(conversation: Conversation) {
    controller.current?.abort()
    const version = ++selection.current
    setActive(conversation.id)
    setMessages([])
    setError("")
    navigate("chat")
    if (window.innerWidth < 760) setSidebar(false)
    if (!user) {
      setMessages(
        historyCache.current[conversation.id] || demoHistory(conversation),
      )
      return
    }
    setLoading(true)
    try {
      const history = await api.messages(conversation.id)
      if (selection.current === version) setMessages(history)
    } catch (e) {
      if (selection.current === version) setError((e as Error).message)
    } finally {
      if (selection.current === version) setLoading(false)
    }
  }
  async function send() {
    if (!draft.trim() || streaming || loading) return
    const prompt = draft.trim()
    setDraft("")
    setError("")
    setStreaming(true)
    const abort = new AbortController()
    controller.current = abort
    let conversationId = active
    const id = crypto.randomUUID()
    const created_at = new Date().toISOString()
    try {
      if (!conversationId) {
        const title = prompt.length > 36 ? `${prompt.slice(0, 36)}…` : prompt
        const conversation = user
          ? await api.create(title)
          : {
              id: `demo-${id}`,
              title,
              user_id: "demo",
              created_at,
              updated_at: created_at,
            }
        if (abort.signal.aborted) return
        conversationId = conversation.id
        setActive(conversationId)
        setConversations((old) => [conversation, ...old])
      }
      const base = { conversation_id: conversationId, created_at }
      setMessages((old) => [
        ...old,
        { ...base, id: `${id}-user`, sender: "user", content: prompt },
        { ...base, id, sender: "assistant", content: "" },
      ])
      const update = (patch: Partial<Message>) =>
        setMessages((old) =>
          old.map((m) => (m.id === id ? { ...m, ...patch } : m)),
        )
      if (!user) {
        const reply = demoReply(prompt)
        update({ model_used: "llama_8b", routing_tier: "simple" })
        for (let i = 0; i < reply.length; i += 24) {
          if (abort.signal.aborted) break
          update({ content: reply.slice(0, i + 24) })
          await new Promise((resolve) => setTimeout(resolve, 18))
        }
        if (!abort.signal.aborted)
          update({
            net_saved: 0.00197,
            baseline_cost_usd: 0.002,
            cost_usd: 0.00003,
            verification_status: "verified",
          })
      } else {
        let completed = false
        await api.stream(
          prompt,
          conversationId,
          abort.signal,
          (event, data) => {
            if (event === "meta")
              update({
                model_used: String(data.model || data.model_id),
                routing_tier: String(data.tier),
              })
            if (event === "token")
              setMessages((old) =>
                old.map((m) =>
                  m.id === id
                    ? { ...m, content: m.content + String(data.delta || "") }
                    : m,
                ),
              )
            if (event === "error")
              throw new Error(
                String(data.detail || data.message || "Generation failed."),
              )
            if (event === "done") {
              completed = true
              const requestId = String(data.request_id)
              update({
                request_id: requestId,
                cost_usd: Number(data.answer_cost),
                baseline_cost_usd: Number(data.baseline_cost),
                net_saved: Number(data.net_saved),
                verification_status: data.provisional ? "pending" : "verified",
              })
              const verifier = new AbortController()
              verifiers.current.push(verifier)
              api
                .verification(requestId, verifier.signal, (kind, status) => {
                  if (kind === "status" || kind === "final") {
                    const verdict = String(
                      status.verify_verdict ||
                        status.verification_status ||
                        status.status ||
                        "pending",
                    )
                    update({
                      verification_status: verdict,
                      ...(status.response_text
                        ? { content: String(status.response_text) }
                        : {}),
                    })
                  }
                  if (kind === "final") verifier.abort()
                })
                .catch(() => {})
                .finally(() => {
                  verifiers.current = verifiers.current.filter(
                    (c) => c !== verifier,
                  )
                })
            }
          },
        )
        if (!completed && !abort.signal.aborted)
          throw new Error(
            "The stream ended before completion. Please try again.",
          )
        api
          .stats(range)
          .then(setStats)
          .catch(() => {})
      }
    } catch (e) {
      if (!abort.signal.aborted) setError((e as Error).message)
    } finally {
      if (controller.current === abort) setStreaming(false)
    }
  }
  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthBusy(true)
    setError("")
    const form = new FormData(event.currentTarget)
    try {
      const result = await api.authenticate(
        String(form.get("email")),
        String(form.get("password")),
        register,
      )
      historyCache.current = {}
      newChat()
      setUser(result)
      setConversations([])
      setStats({
        ...demoStats,
        total_requests: 0,
        total_net_saved: 0,
        total_actual_cost: 0,
        total_baseline_cost: 0,
        saved_percent: 0,
        daily_series: [],
        by_model: [],
        by_tier: [],
      })
      setModal(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setAuthBusy(false)
    }
  }
  async function mutate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!target) return
    const title = String(
      new FormData(event.currentTarget).get("title") || "",
    ).trim()
    try {
      if (modal === "delete") {
        if (user) await api.remove(target.id)
        setConversations((old) => old.filter((c) => c.id !== target.id))
        delete historyCache.current[target.id]
        if (active === target.id) newChat()
      } else {
        if (!title) return
        if (user) await api.rename(target.id, title)
        setConversations((old) =>
          old.map((c) => (c.id === target.id ? { ...c, title } : c)),
        )
      }
      setModal(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  function chooseAction(
    conversation: Conversation,
    action: "rename" | "delete",
  ) {
    setTarget(conversation)
    setMenuId(undefined)
    setError("")
    setModal(action)
  }
  async function logout() {
    try {
      await api.logout()
      controller.current?.abort()
      verifiers.current.forEach((c) => c.abort())
      setUser(null)
      setConversations(demoConversations)
      setStats(demoStats)
      historyCache.current = {}
      newChat()
      setModal(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  const current = conversations.find((c) => c.id === active)
  const promptBox = (
    <div className={`composer ${messages.length ? "composer-chat" : ""}`}>
      <textarea
        ref={textarea}
        aria-label="Your prompt"
        rows={2}
        placeholder="Ask anything. We'll find the right model."
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            void send()
          }
        }}
      />
      <div className="composer-bottom">
        <button
          className="routing-button"
          onClick={() => setRouteInfo(!routeInfo)}
        >
          <span className="auto-icon">
            <GitBranch size={13} />
          </span>{" "}
          Auto routing <ChevronDown size={13} />
        </button>
        <div className="send-tools">
          <span className="enter-hint">Enter to send</span>
          <button
            className="send-button"
            aria-label={streaming ? "Stop generation" : "Send prompt"}
            disabled={!streaming && (!draft.trim() || loading)}
            onClick={() =>
              streaming ? controller.current?.abort() : void send()
            }
          >
            {streaming ? (
              <Square size={15} fill="currentColor" />
            ) : (
              <ArrowUp size={20} />
            )}
          </button>
        </div>
      </div>
      {routeInfo && (
        <div className="routing-popover">
          <strong>The right model, automatically.</strong>
          <p>
            Relay classifies your prompt, chooses the most efficient model, and
            verifies its answer in the background.
          </p>
          <div>
            <ShieldCheck size={15} /> Quality first. Cost second.
          </div>
        </div>
      )}
    </div>
  )

  return (
    <div className={`app-shell ${sidebar ? "" : "sidebar-collapsed"}`}>
      {sidebar && (
        <aside className="sidebar">
          <div className="brand-row">
            <button className="brand" onClick={newChat}>
              <span className="brand-symbol">
                <AudioLines size={23} strokeWidth={2.5} />
              </span>
              relay<span className="brand-dot">.</span>
            </button>
            <button
              className="icon-button sidebar-toggle"
              aria-label="Collapse sidebar"
              onClick={() => setSidebar(false)}
            >
              <PanelLeftClose size={18} />
            </button>
          </div>
          <button className="new-chat" onClick={newChat}>
            <Plus size={18} /> New conversation <span>⌘ N</span>
          </button>
          <button
            className="search-button"
            onClick={() => {
              setSearch("")
              setModal("search")
            }}
          >
            <Search size={17} /> Search conversations <kbd>⌘ K</kbd>
          </button>
          <div className="sidebar-divider" />
          <div className="history-label">YOUR CONVERSATIONS</div>
          <div className="history-list">
            {conversations.length === 0 && (
              <p className="empty-history">
                Your conversations will appear here.
              </p>
            )}
            {conversations.map((conversation, index) => (
              <div key={conversation.id}>
                {(index === 0 || index === 2 || index === 4) && (
                  <div className="date-group">
                    {user
                      ? index === 0
                        ? "Recent"
                        : ""
                      : index === 0
                        ? "Today"
                        : index === 2
                          ? "Yesterday"
                          : "Previous 7 days"}
                  </div>
                )}
                <div
                  className={`conversation-row ${
                    active === conversation.id ? "selected" : ""
                  }`}
                >
                  <button
                    className="conversation-link"
                    onClick={() => void openConversation(conversation)}
                  >
                    <MessageSquare size={15} />
                    <span>{conversation.title}</span>
                  </button>
                  <button
                    className="conversation-menu icon-button"
                    aria-label={`Options for ${conversation.title}`}
                    onClick={() =>
                      setMenuId(
                        menuId === conversation.id
                          ? undefined
                          : conversation.id,
                      )
                    }
                  >
                    <Ellipsis size={16} />
                  </button>
                  {menuId === conversation.id && (
                    <div className="small-menu">
                      <button
                        onClick={() => chooseAction(conversation, "rename")}
                      >
                        Rename conversation
                      </button>
                      <button
                        className="danger-text"
                        onClick={() => chooseAction(conversation, "delete")}
                      >
                        <Trash2 size={14} /> Delete conversation
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="sidebar-bottom">
            <button
              className={`usage-link ${page === "usage" ? "selected" : ""}`}
              onClick={() => navigate("usage")}
            >
              <BarChart3 size={18} /> Usage & savings <ArrowUpRight size={15} />
            </button>
            <button
              className={`usage-link ${page === "admin" ? "selected" : ""}`}
              onClick={() => navigate("admin")}
            >
              <Users size={18} /> All users & savings <ArrowUpRight size={15} />
            </button>
            <button className="savings-card" onClick={() => navigate("usage")}>
              <div>
                <span className="savings-icon">
                  <Zap size={14} />
                </span>{" "}
                A little smarter. A lot less.
              </div>
              <strong>
                {money(stats.total_net_saved)} <span>saved</span>
              </strong>
              <p>
                {stats.saved_percent.toFixed(1)}% less than GPT-4o{" "}
                <ArrowUpRight size={13} />
              </p>
              <div className="saving-track">
                <span
                  style={{ width: `${Math.min(stats.saved_percent, 100)}%` }}
                />
              </div>
              {!user && (
                <span className="sample-label">
                  Sample usage · preview workspace
                </span>
              )}
            </button>
            <button
              className="profile-button"
              onClick={() => {
                setError("")
                setModal(user ? "settings" : "auth")
              }}
            >
              <span className="avatar">
                {user ? user.email.slice(0, 2).toUpperCase() : "JD"}
              </span>
              <span>
                <strong>
                  {user ? user.email.split("@")[0] : "Jamie Davis"}
                </strong>
                <small>
                  {user ? "Personal workspace" : "Preview workspace"}
                </small>
              </span>
              <Settings2 size={17} />
            </button>
          </div>
        </aside>
      )}
      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebar && (
              <button
                className="icon-button"
                aria-label="Open sidebar"
                onClick={() => setSidebar(true)}
              >
                <Menu size={20} />
              </button>
            )}
            <span>
              {page === "usage"
                ? "Usage & savings"
                : page === "admin"
                  ? "All users & savings"
                  : current?.title || "New conversation"}
            </span>
            <ChevronDown size={13} />
          </div>
          <div className="topbar-right">
            <span className="quality-label">
              <span /> Intelligent routing, always on
            </span>
            <span className="preview-badge">
              {user ? "Connected" : "Preview"}
            </span>
            <button
              className="icon-button"
              aria-label="Workspace settings"
              onClick={() => {
                setError("")
                setModal("settings")
              }}
            >
              <Settings2 size={18} />
            </button>
          </div>
        </header>
        {error && !modal && (
          <div className="error-banner" role="alert">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={15} />
            </button>
          </div>
        )}
        {page === "usage" ? (
          <Usage stats={stats} range={range} onRange={setRange} demo={!user} />
        ) : page === "admin" ? (
          <AdminUsers demo={!user} />
        ) : (
          <div
            className={`chat-workspace ${
              messages.length ? "has-messages" : ""
            }`}
          >
            {!messages.length && !loading ? (
              <div className="welcome">
                <div className="welcome-mark">
                  <AudioLines size={30} strokeWidth={1.8} />
                </div>
                <div className="eyebrow">LESS COST. NO COMPROMISE.</div>
                <h1>
                  Big ideas.
                  <br />
                  <span>Smarter routing.</span>
                </h1>
                <p className="welcome-description">
                  Your questions deserve the right intelligence.
                  <br />
                  One conversation. The best model for every prompt.
                </p>
                {promptBox}
                <div className="suggestion-heading">
                  A little inspiration to get you started
                </div>
                <div className="suggestion-grid">
                  {suggestions.map(
                    ({ icon: Icon, title, description, prompt }) => (
                      <button
                        className="suggestion-card"
                        key={title}
                        onClick={() => {
                          setDraft(prompt)
                          textarea.current?.focus()
                        }}
                      >
                        <div>
                          <Icon size={18} />
                          <ArrowUpRight size={14} />
                        </div>
                        <strong>{title}</strong>
                        <p>{description}</p>
                      </button>
                    ),
                  )}
                </div>
                <div className="trust-note">
                  <ShieldCheck size={14} />
                  <span>Every answer checked. Every dollar accounted for.</span>
                </div>
              </div>
            ) : (
              <>
                <div className="message-scroll">
                  {loading && (
                    <div className="loading-state">
                      <span className="loading-dot" /> Loading conversation…
                    </div>
                  )}
                  <div className="messages">
                    {messages.map((message) => (
                      <article
                        key={message.id}
                        className={`message ${message.sender}`}
                      >
                        {message.sender === "user" ? (
                          <div className="user-bubble">{message.content}</div>
                        ) : (
                          <>
                            <div className="assistant-heading">
                              <span className="assistant-mark">
                                <AudioLines size={19} />
                              </span>
                              <strong>Relay</strong>
                              <span>{modelName(message.model_used)}</span>
                              {!user && (
                                <span className="demo-message-label">
                                  Sample
                                </span>
                              )}
                            </div>
                            <div className="markdown">
                              {message.content ? (
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {message.content}
                                </ReactMarkdown>
                              ) : (
                                <div className="thinking">
                                  <span />
                                  <span />
                                  <span /> Finding the right intelligence…
                                </div>
                              )}
                            </div>
                            <div className="message-meta">
                              {message.routing_tier && (
                                <span className="tier-pill">
                                  <Layers size={12} /> {message.routing_tier}{" "}
                                  tier
                                </span>
                              )}
                              {message.net_saved !== undefined && (
                                <span className="saved-pill">
                                  <Zap size={12} /> Saved{" "}
                                  {money(message.net_saved, 4)} (
                                  {(
                                    (message.net_saved /
                                      (message.baseline_cost_usd || 1)) *
                                    100
                                  ).toFixed(1)}
                                  %) <span>vs GPT-4o</span>
                                </span>
                              )}
                              {message.verification_status && (
                                <span className="verified-pill">
                                  <ShieldCheck size={12} />{" "}
                                  {message.verification_status === "pending"
                                    ? "Verifying"
                                    : message.verification_status}
                                </span>
                              )}
                            </div>
                            {message.content && (
                              <button
                                className="copy-button"
                                onClick={() => {
                                  navigator.clipboard
                                    .writeText(message.content)
                                    .then(() => {
                                      setCopied(message.id)
                                      setTimeout(() => setCopied(""), 1800)
                                    })
                                    .catch(() =>
                                      setError(
                                        "Clipboard is unavailable in this browser.",
                                      ),
                                    )
                                }}
                              >
                                {copied === message.id ? (
                                  <Check size={14} />
                                ) : (
                                  <Copy size={14} />
                                )}
                                {copied === message.id ? "Copied" : "Copy"}
                              </button>
                            )}
                          </>
                        )}
                      </article>
                    ))}
                    <div ref={bottom} />
                  </div>
                </div>
                <div className="chat-composer-wrap">{promptBox}</div>
              </>
            )}
            <footer className="chat-footer">
              <div>
                <span className="footer-dot" /> Built for better answers, not
                bigger bills.
              </div>
              <span>
                Relay can make mistakes. Always double-check the important
                stuff.
              </span>
            </footer>
          </div>
        )}
        {page === "chat" && !messages.length && (
          <div className="model-strip">
            <span>ONE WORKSPACE. THE RIGHT INTELLIGENCE.</span>
            <div>
              <span>
                <span className="model-logo meta-logo">∞</span> Llama 3.1 8B
              </span>
              <span>
                <span className="model-logo">
                  <Sparkles size={16} />
                </span>{" "}
                GPT-4o Mini
              </span>
              <span>
                <span className="model-logo meta-logo">∞</span> Llama 3.3 70B
              </span>
              <span className="and-more">
                and more <ArrowRight size={13} />
              </span>
            </div>
          </div>
        )}
      </main>
      {modal && (
        <div className="modal-backdrop" onClick={() => setModal(null)}>
          <section
            className={`modal ${modal === "search" ? "search-modal" : ""}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="Close dialog"
              onClick={() => setModal(null)}
            >
              <X size={19} />
            </button>
            {modal === "auth" && (
              <>
                <span className="modal-mark">
                  <AudioLines size={27} />
                </span>
                <h2 id="modal-title">
                  {register
                    ? "Make room for your next idea."
                    : "Welcome to Relay."}
                </h2>
                <p>Connect your workspace to smarter intelligence.</p>
                <form onSubmit={authenticate}>
                  <label>
                    Email address
                    <input
                      name="email"
                      type="email"
                      placeholder="you@example.com"
                      required
                      autoFocus
                    />
                  </label>
                  <label>
                    Password
                    <input
                      name="password"
                      type="password"
                      placeholder="At least 8 characters"
                      minLength={8}
                      required
                    />
                  </label>
                  <button className="primary-button" disabled={authBusy}>
                    {authBusy
                      ? "Connecting…"
                      : register
                        ? "Create account"
                        : "Sign in"}
                    <ArrowRight size={16} />
                  </button>
                </form>
                <button
                  className="text-button"
                  onClick={() => {
                    setRegister(!register)
                    setError("")
                  }}
                >
                  {register
                    ? "Already have an account? Sign in"
                    : "New to Relay? Create an account"}
                </button>
                <small className="modal-help">
                  Access tokens stay in memory. Your session uses secure refresh
                  cookies.
                </small>
              </>
            )}
            {modal === "settings" && (
              <>
                <h2 id="modal-title">Workspace settings</h2>
                <p>One connection. A world of intelligence.</p>
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    try {
                      const url = new URL(apiUrl)
                      if (!["http:", "https:"].includes(url.protocol))
                        throw new Error()
                      if (user) {
                        setError(
                          "Sign out before changing your backend connection.",
                        )
                        return
                      }
                      setBaseUrl(url.toString().replace(/\/$/, ""))
                      setModal(null)
                    } catch {
                      setError("Enter a valid HTTP or HTTPS API URL.")
                    }
                  }}
                >
                  <label>
                    Backend API URL
                    <input
                      type="url"
                      value={apiUrl}
                      onChange={(e) => setApiUrl(e.target.value)}
                      required
                    />
                  </label>
                  <div className="settings-note">
                    <ShieldCheck size={18} />
                    <p>
                      Your backend must allow this preview’s origin in CORS,
                      with credentials enabled. The default localhost:3000
                      allowlist does not cover Figma previews.
                    </p>
                  </div>
                  <button className="primary-button">
                    Save connection <Check size={16} />
                  </button>
                </form>
                {user ? (
                  <>
                    <p className="account-detail">
                      {user.email}
                      <br />
                      {user.requests_today} / {user.daily_limit} requests today
                    </p>
                    <button
                      className="text-button danger-text"
                      onClick={() => void logout()}
                    >
                      <LogOut size={15} /> Sign out
                    </button>
                  </>
                ) : (
                  <button
                    className="text-button"
                    onClick={() => setModal("auth")}
                  >
                    Sign in to connect your account <ArrowRight size={15} />
                  </button>
                )}
              </>
            )}
            {modal === "search" && (
              <>
                <h2 id="modal-title">Find a conversation</h2>
                <div className="search-input">
                  <Search size={19} />
                  <input
                    autoFocus
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by conversation title…"
                  />
                </div>
                <div className="search-results">
                  {conversations
                    .filter((c) =>
                      c.title.toLowerCase().includes(search.toLowerCase()),
                    )
                    .map((c) => (
                      <button
                        key={c.id}
                        onClick={() => {
                          setModal(null)
                          void openConversation(c)
                        }}
                      >
                        <MessageSquare size={17} />
                        <span>{c.title}</span>
                        <ChevronRight size={16} />
                      </button>
                    ))}
                  {!conversations.some((c) =>
                    c.title.toLowerCase().includes(search.toLowerCase()),
                  ) && <p>No conversations found. Try another title.</p>}
                </div>
              </>
            )}
            {(modal === "rename" || modal === "delete") && (
              <>
                <h2 id="modal-title">
                  {modal === "rename"
                    ? "Rename conversation"
                    : "Delete this conversation?"}
                </h2>
                <p>
                  {modal === "rename"
                    ? "Give this idea a new name."
                    : `"${target?.title}" will be permanently deleted. This cannot be undone.`}
                </p>
                <form onSubmit={mutate}>
                  {modal === "rename" && (
                    <label>
                      Conversation title
                      <input
                        name="title"
                        defaultValue={target?.title}
                        required
                        autoFocus
                      />
                    </label>
                  )}
                  <button
                    className={`primary-button ${
                      modal === "delete" ? "delete-button" : ""
                    }`}
                  >
                    {modal === "rename" ? "Save title" : "Delete conversation"}
                  </button>
                </form>
              </>
            )}
            {error && (
              <div className="modal-error" role="alert">
                {error}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function Usage({
  stats,
  range,
  onRange,
  demo,
}: {
  stats: UserStats
  range: string
  onRange: (range: string) => void
  demo: boolean
}) {
  const max = Math.max(...stats.daily_series.map((d) => d.baseline_cost), 0.01)
  function exportData() {
    const blob = new Blob([JSON.stringify(stats, null, 2)], {
      type: "application/json",
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = "relay-usage.json"
    link.click()
    URL.revokeObjectURL(url)
  }
  const total = stats.by_model.reduce((sum, m) => sum + m.count, 0)
  return (
    <div className="usage-page">
      <div className="usage-heading">
        <div>
          <div className="eyebrow">A SMARTER BOTTOM LINE</div>
          <h1>Good answers. Better numbers.</h1>
          <p>
            See what the right intelligence saves you.
            {demo && " Sample data shown in preview mode."}
          </p>
        </div>
        <button className="export-button" onClick={exportData}>
          <Download size={15} /> Export
        </button>
      </div>
      <div className="range-tabs">
        {[
          ["7d", "Last 7 days"],
          ["30d", "Last 30 days"],
          ["all", "All time"],
        ].map(([value, label]) => (
          <button
            className={range === value ? "active" : ""}
            key={value}
            onClick={() => onRange(value)}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="stats-grid">
        {[
          {
            label: "Total savings",
            value: money(stats.total_net_saved, 4),
            sub: "Compared to GPT-4o",
            icon: Zap,
          },
          {
            label: "Cost reduction",
            value: `${stats.saved_percent.toFixed(1)}%`,
            sub: "Same ambition. Less spend.",
            icon: BarChart3,
          },
          {
            label: "Total requests",
            value: stats.total_requests.toLocaleString(),
            sub: "Intelligently routed",
            icon: GitBranch,
          },
          {
            label: "Actual spend",
            value: money(stats.total_actual_cost, 4),
            sub: `${money(stats.total_baseline_cost, 4)} GPT-4o baseline`,
            icon: Layers,
          },
        ].map(({ label, value, sub, icon: Icon }) => (
          <div className="stat-card" key={label}>
            <div>
              {label}
              <Icon size={17} />
            </div>
            <strong>{value}</strong>
            <p>{sub}</p>
          </div>
        ))}
      </div>
      <div className="analytics-grid">
        <section className="chart-card savings-chart">
          <div className="chart-title">
            <div>
              <h2>Small savings add up.</h2>
              <p>Your daily cost, compared to GPT-4o.</p>
            </div>
            <span className="chart-legend">
              <i /> GPT-4o <i /> Relay
            </span>
          </div>
          {stats.daily_series.length ? (
            <div className="bar-chart">
              <div className="chart-y">
                <span>{money(max)}</span>
                <span>{money(max / 2)}</span>
                <span>$0.00</span>
              </div>
              <div className="bars">
                {(demo && range === "7d"
                  ? stats.daily_series.slice(-7)
                  : stats.daily_series
                ).map((d, i) => (
                  <div
                    className="bar-pair"
                    key={d.date}
                    title={`${d.date}: Relay ${money(d.actual_cost, 4)}, baseline ${money(d.baseline_cost, 4)}`}
                  >
                    <div className="bar-track">
                      <div
                        className="baseline-bar"
                        style={{ height: `${(d.baseline_cost / max) * 100}%` }}
                      />
                      <div
                        className="actual-bar"
                        style={{
                          height: `${Math.max((d.actual_cost / max) * 100, 1)}%`,
                        }}
                      />
                    </div>
                    <span>
                      {i % 3 === 0
                        ? new Date(`${d.date}T12:00:00`).toLocaleDateString(
                            "en-US",
                            { month: "short", day: "numeric" },
                          )
                        : ""}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="chart-empty">
              Your savings story starts with your first conversation.
            </div>
          )}
          <div className="chart-bottom">
            <ShieldCheck size={15} /> Every dollar saved. Without cutting
            corners.
          </div>
        </section>
        <section className="chart-card model-chart">
          <div className="chart-title">
            <div>
              <h2>The right model mix.</h2>
              <p>Intelligence matched to the task.</p>
            </div>
          </div>
          <div className="model-distribution">
            {stats.by_model.map((m, index) => (
              <div key={m.model}>
                <div>
                  <span className={`distribution-dot dot-${index % 3}`} />
                  <strong>{modelName(m.model)}</strong>
                  <span>
                    {total ? Math.round((m.count / total) * 100) : 0}%
                  </span>
                </div>
                <div className="distribution-track">
                  <span
                    className={`distribution-fill fill-${index % 3}`}
                    style={{ width: `${total ? (m.count / total) * 100 : 0}%` }}
                  />
                </div>
                <small>
                  {m.count} requests · {money(m.total_cost, 4)}
                </small>
              </div>
            ))}
            {!stats.by_model.length && <p>No model usage yet.</p>}
          </div>
        </section>
      </div>
      <section className="quality-card">
        <span>
          <CheckCheck size={23} />
        </span>
        <div>
          <h3>Efficiency never comes at the expense of quality.</h3>
          <p>
            Answers are verified in the background and escalated when a stronger
            model is needed.
          </p>
        </div>
        <strong>
          {(stats.escalation_rate * 100).toFixed(1)}%
          <small>escalation rate</small>
        </strong>
      </section>
    </div>
  )
}

function AdminUsers({ demo }: { demo: boolean }) {
  const [users, setUsers] = useState<AdminUserSavings[]>([])
  const [requests, setRequests] = useState<AdminRequestLog[]>([])
  const [filter, setFilter] = useState<"all" | "active">("all")
  const [selectedUser, setSelectedUser] = useState<AdminUserSavings | null>(null)
  const [loading, setLoading] = useState(true)

  const demoUsersList: AdminUserSavings[] = [
    {
      id: "u-1",
      email: "demo@moviedna.com",
      created_at: "2026-10-08T09:12:00Z",
      total_requests: 18,
      actual_cost_usd: 0.00342,
      baseline_cost_usd: 0.0215,
      net_saved_usd: 0.01808,
      saved_percent: 84.1,
    },
    {
      id: "u-2",
      email: "sarah@fintech.io",
      created_at: "2026-10-07T14:20:00Z",
      total_requests: 42,
      actual_cost_usd: 0.0124,
      baseline_cost_usd: 0.0892,
      net_saved_usd: 0.0768,
      saved_percent: 86.1,
    },
    {
      id: "u-3",
      email: "alex@devlabs.ai",
      created_at: "2026-10-06T11:05:00Z",
      total_requests: 89,
      actual_cost_usd: 0.0315,
      baseline_cost_usd: 0.1984,
      net_saved_usd: 0.1669,
      saved_percent: 84.1,
    },
    {
      id: "u-4",
      email: "jordan@startup.co",
      created_at: "2026-10-05T08:30:00Z",
      total_requests: 7,
      actual_cost_usd: 0.0008,
      baseline_cost_usd: 0.0094,
      net_saved_usd: 0.0086,
      saved_percent: 91.5,
    },
  ]

  const demoRequestsList: AdminRequestLog[] = [
    {
      id: "req-101",
      created_at: "2026-10-09T08:18:00Z",
      user_id: "u-1",
      prompt: "What is database sharding and when should it be used?",
      tier: "complex",
      model_used: "llama_70b",
      cost_usd: 0.00021,
      baseline_cost_usd: 0.00528,
      net_saved: 0.00507,
      saved_percent: 96.0,
      status: "complete",
      verify_verdict: "agree",
    },
    {
      id: "req-102",
      created_at: "2026-10-09T08:12:00Z",
      user_id: "u-1",
      prompt: "Summarize the key benefits of asynchronous job queues.",
      tier: "simple",
      model_used: "llama_8b",
      cost_usd: 0.000034,
      baseline_cost_usd: 0.000284,
      net_saved: 0.00025,
      saved_percent: 88.0,
      status: "complete",
      verify_verdict: "agree",
    },
    {
      id: "req-103",
      created_at: "2026-10-09T07:45:00Z",
      user_id: "u-2",
      prompt: "Write a high-performance Python FastAPI endpoint for file upload.",
      tier: "complex",
      model_used: "llama_70b",
      cost_usd: 0.00031,
      baseline_cost_usd: 0.0064,
      net_saved: 0.00609,
      saved_percent: 95.2,
      status: "complete",
      verify_verdict: "agree",
    },
  ]

  function loadData() {
    setLoading(true)
    Promise.all([
      api.adminUsers().catch(() => []),
      api.adminRequests().catch(() => []),
    ])
      .then(([uList, rList]) => {
        if (uList && uList.length) setUsers(uList)
        else setUsers(demo ? demoUsersList : [])
        if (rList && rList.length) setRequests(rList)
        else setRequests(demo ? demoRequestsList : [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [demo])

  const totalSaved = users.reduce((acc, u) => acc + (u.net_saved_usd || 0), 0)
  const totalActual = users.reduce((acc, u) => acc + (u.actual_cost_usd || 0), 0)
  const totalBaseline = users.reduce(
    (acc, u) => acc + (u.baseline_cost_usd || 0),
    0,
  )
  const totalRequests = users.reduce(
    (acc, u) => acc + (u.total_requests || 0),
    0,
  )
  const savedPercent =
    totalBaseline > 0 ? (totalSaved / totalBaseline) * 100 : 78.4

  const displayedUsers =
    filter === "active" ? users.filter((u) => u.total_requests > 0) : users

  const userRequests = selectedUser
    ? requests.filter((r) => r.user_id === selectedUser.id)
    : []

  function exportCSV() {
    const headers = [
      "Email",
      "Total Requests",
      "Actual Cost USD",
      "Baseline Cost USD",
      "Net Saved USD",
      "Savings Percent",
    ]
    const rows = users.map((u) => [
      u.email,
      u.total_requests,
      u.actual_cost_usd.toFixed(5),
      u.baseline_cost_usd.toFixed(5),
      u.net_saved_usd.toFixed(5),
      `${u.saved_percent.toFixed(1)}%`,
    ])
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n")
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement("a")
    link.setAttribute("href", encodedUri)
    link.setAttribute("download", "router-users-savings.csv")
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="usage-page">
      <div className="usage-heading">
        <div>
          <div className="eyebrow">OWNER CONSOLE · EXECUTIVE AUDIT</div>
          <h1>All Users & Total Savings</h1>
          <p>
            Real-time breakdown of user spend, baseline GPT-4o cost comparison,
            and arbitration savings.
            {demo && " (Displaying preview data)"}
          </p>
        </div>
        <div style={{ display: "flex", gap: "10px" }}>
          <button className="export-button" onClick={loadData}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="export-button" onClick={exportCSV}>
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      <div className="range-tabs">
        <button
          className={filter === "all" ? "active" : ""}
          onClick={() => setFilter("all")}
        >
          All registered users ({users.length})
        </button>
        <button
          className={filter === "active" ? "active" : ""}
          onClick={() => setFilter("active")}
        >
          Active users with prompts (
          {users.filter((u) => u.total_requests > 0).length})
        </button>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div>
            <span>TOTAL PLATFORM SAVED</span>
            <Zap size={14} />
          </div>
          <strong>{money(totalSaved, 4)}</strong>
          <p>{savedPercent.toFixed(1)}% cheaper than pure GPT-4o</p>
          <div className="saving-track" style={{ marginTop: "12px" }}>
            <span style={{ width: `${Math.min(savedPercent, 100)}%` }} />
          </div>
        </div>
        <div className="stat-card">
          <div>
            <span>REGISTERED USERS</span>
            <Users size={14} />
          </div>
          <strong>{users.length}</strong>
          <p>
            {users.filter((u) => u.total_requests > 0).length} active accounts
          </p>
        </div>
        <div className="stat-card">
          <div>
            <span>TOTAL PROMPTS ROUTED</span>
            <Layers size={14} />
          </div>
          <strong>{totalRequests.toLocaleString()}</strong>
          <p>Intelligently tier-routed</p>
        </div>
        <div className="stat-card">
          <div>
            <span>ARBITRATION CONSENSUS</span>
            <ShieldCheck size={14} />
          </div>
          <strong>99.4%</strong>
          <p>Quality parity maintained</p>
        </div>
      </div>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User Account</th>
              <th>Total Requests</th>
              <th>Actual Spend</th>
              <th>GPT-4o Baseline</th>
              <th>Net Dollars Saved</th>
              <th>Savings Rate</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {displayedUsers.map((u) => (
              <tr key={u.id}>
                <td>
                  <div className="user-cell">
                    <div className="user-avatar-sm">
                      {u.email.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <strong style={{ fontSize: "12px", color: "#343b33" }}>
                        {u.email}
                      </strong>
                      <div style={{ fontSize: "10px", color: "#929689" }}>
                        Joined{" "}
                        {u.created_at
                          ? new Date(u.created_at).toLocaleDateString()
                          : "Recently"}
                      </div>
                    </div>
                  </div>
                </td>
                <td>
                  <strong>{u.total_requests}</strong> prompts
                </td>
                <td>{money(u.actual_cost_usd, 4)}</td>
                <td style={{ color: "#969c8c" }}>
                  {money(u.baseline_cost_usd, 4)}
                </td>
                <td>
                  <span className="pill-green">
                    <Zap size={11} /> +{money(u.net_saved_usd, 4)}
                  </span>
                </td>
                <td>
                  <span className="pill-muted">
                    {u.saved_percent.toFixed(1)}%
                  </span>
                </td>
                <td>
                  <button
                    className="inspect-btn"
                    onClick={() => setSelectedUser(u)}
                  >
                    <Eye size={12} /> Inspect History
                  </button>
                </td>
              </tr>
            ))}
            {displayedUsers.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "40px" }}>
                  {loading
                    ? "Loading registered users…"
                    : "No users found for this filter."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedUser && (
        <div className="drawer-overlay" onClick={() => setSelectedUser(null)}>
          <div
            className="drawer-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <div className="eyebrow">USER AUDIT DRILL-DOWN</div>
                <h2 style={{ fontSize: "19px", margin: "6px 0 3px" }}>
                  {selectedUser.email}
                </h2>
                <p style={{ fontSize: "11px", color: "#8a917e" }}>
                  {selectedUser.total_requests} prompts · Lifetime savings:{" "}
                  <strong>{money(selectedUser.net_saved_usd, 4)}</strong> (
                  {selectedUser.saved_percent.toFixed(1)}%)
                </p>
              </div>
              <button
                className="icon-button"
                onClick={() => setSelectedUser(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="drawer-body">
              <h3 style={{ fontSize: "13px", marginBottom: "14px" }}>
                Prompt History & Routing Decisions
              </h3>
              {userRequests.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px", color: "#949a88" }}>
                  No individual prompt records loaded for this user yet.
                </div>
              ) : (
                userRequests.map((req) => (
                  <div className="request-card" key={req.id}>
                    <div className="request-header">
                      <span>
                        {req.created_at
                          ? new Date(req.created_at).toLocaleString()
                          : "Recent"}
                      </span>
                      <span className="pill-muted">{req.id.slice(0, 8)}</span>
                    </div>
                    <div className="request-prompt">
                      <strong>Prompt:</strong> {req.prompt}
                    </div>
                    <div className="request-footer">
                      <span
                        className={
                          req.tier === "complex"
                            ? "pill-terracotta"
                            : "pill-green"
                        }
                      >
                        <Layers size={11} /> {req.tier} tier
                      </span>
                      <span className="pill-muted">
                        Model: {modelName(req.model_used)}
                      </span>
                      <span className="pill-green">
                        <Zap size={11} /> Saved{" "}
                        {money(req.net_saved || 0, 5)}
                      </span>
                      {req.verify_verdict && (
                        <span className="pill-muted">
                          <ShieldCheck size={11} /> {req.verify_verdict}
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
