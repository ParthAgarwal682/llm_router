# Relay

A React, Vite, and Tailwind frontend for the LLM Router & Arbitration API.

## Backend connection

- The default API URL is `http://localhost:8000`.
- Set `VITE_API_BASE_URL` in your environment, or change the URL in Workspace settings.
- Sign in or create an account to use the real backend. Before sign-in, the workspace uses clearly labeled sample conversations, sample savings, and simulated responses. Preview changes are held in memory only.
- JWT access tokens are held in memory. Refresh cookies are sent with `credentials: 'include'`; eligible 401 responses refresh and retry once.

### CORS and cookies

The backend's default allowlist (`localhost:3000`) does not cover the Figma preview. Add the actual frontend origin to the FastAPI CORS allowlist and enable credentials. For an HTTPS preview, use an HTTPS-reachable backend, rather than an HTTP localhost service. Cross-site refresh cookies may require `SameSite=None; Secure`, and browser third-party cookie restrictions still apply. A same-site deployment or reverse proxy is preferable.

## Features

- Auto-routing chat with POST SSE streaming, cancellation, Markdown, tables, and code blocks.
- Background request verification, tier/model metadata, and per-answer savings.
- Conversation create, search, rename, delete, and correctly unpacked request history.
- `/usage` dashboard with range selection, cost comparison, model distribution, and JSON export.
- Responsive, collapsible sidebar. Enter sends, Shift+Enter adds a line, and Cmd/Ctrl+K searches.

## Checks

```sh
pnpm exec tsc --noEmit
pnpm build
pnpm format src/App.tsx src/lib/api.ts src/lib/demo.ts
```

The Figma Make development server is already supervised by the host; do not start a second server.
