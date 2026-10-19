# MediChain Frontend

React 18 + Vite UI for the MediChain multi-agent clinical diagnostic system.
The production Docker image builds this app into static assets and serves them
through nginx, which also proxies `/api` and `/ws` to the FastAPI backend.

## Run Locally

```bash
npm install --legacy-peer-deps
npm run dev
```

Local dev runs on `http://localhost:8080` and proxies backend traffic to
`http://localhost:8000`.

## Production Build

```bash
npm run build
```

The compose stack builds the same bundle via `frontend-v3-creative/Dockerfile`
and exposes it at `http://localhost:8080`.

## Tests

```bash
npm test
npm run lint
```

Current coverage focuses on:

- `src/services/api.test.ts`: API error handling, request bodies, delete calls.
- `src/hooks/useWebSocket.test.tsx`: connection lifecycle, event sequencing,
  malformed messages, reconnect behaviour.
- `src/components/DiagnosisPanel.test.tsx`: rendering, confidence ordering,
  safety badges, CDSS score display, evidence toggles.
