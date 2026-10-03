# AI Pulse — Next.js Web App (Phase 1B)

## Getting Started

```bash
cd web
npm install
cp .env.local.example .env.local
npm run dev
```

The web app will run on `http://localhost:3000`.

## Architecture & Security Boundary

- **Server-Side Route Handlers**: Next.js App Router API routes (`/api/feed`, `/api/items/[id]`, `/api/items/[id]/save`, `/api/saved`) run exclusively on the server side.
- **API Secret Key Protection**: `API_SECRET_KEY` is loaded from `.env.local` (server-side ONLY, never prefixed with `NEXT_PUBLIC_*`) and attached to backend HTTP headers (`X-API-Key`).
- **Admin Isolation**: Admin routes (`/admin/*`) are **NOT** proxied by the Next.js API layer.
- **PWA Ready**: Web App Manifest (`public/manifest.json`) and Service Worker (`public/sw.js`) configured for PWA installation.
