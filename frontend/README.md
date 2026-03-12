# Smriti Frontend

The frontend for **Smriti**, an AI-powered Indian legal research platform. Built with Next.js 15 (App Router), TypeScript, Tailwind CSS, and shadcn/ui.

Provides hybrid semantic + keyword search across Indian Supreme Court judgments, interactive citation graph visualization, RAG-powered legal chat, and AI agent workflows for research, case preparation, strategy analysis, and legal drafting.

---

## Prerequisites

- **Node.js** 20+ (LTS recommended)
- **npm** (included with Node.js)
- A running Smriti backend (see `docs/ENV_SETUP.md`)

---

## Setup

```bash
# 1. Install dependencies
npm install

# 2. Create environment file
cp .env.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_URL

# 3. Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Environment Variables

Create a `.env.local` file in the `frontend/` directory:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME=Smriti
NEXT_PUBLIC_APP_DESCRIPTION=Indian Legal Research Platform
```

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL (must include `/api/v1`) |
| `NEXT_PUBLIC_APP_NAME` | No | Application name displayed in UI |
| `NEXT_PUBLIC_APP_DESCRIPTION` | No | Meta description for the application |

---

## Commands

```bash
npm run dev       # Start development server (http://localhost:3000)
npm run build     # Production build
npm run start     # Start production server
npm test          # Run tests (vitest + @testing-library/react)
npm run lint      # Run ESLint
```

**Test suite**: 298 tests covering pages, components, error boundaries, and API integration.

---

## Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router pages
│   │   ├── search/             # Legal search with hybrid results
│   │   ├── case/[id]/          # Case detail view
│   │   ├── chat/               # RAG-powered legal chat
│   │   ├── graph/              # Citation graph visualization
│   │   ├── agents/             # AI agent workflows
│   │   │   ├── research/       # Research agent
│   │   │   ├── case-prep/      # Case preparation agent
│   │   │   ├── strategy/       # Strategy analysis agent
│   │   │   └── drafting/       # Legal drafting agent
│   │   ├── register/           # User registration
│   │   ├── login/              # User login
│   │   └── layout.tsx          # Root layout
│   ├── components/             # Shared UI components
│   │   ├── ui/                 # shadcn/ui primitives
│   │   ├── error-boundary.tsx  # Error boundary with fallback
│   │   └── agent-checkpoint-prompt.tsx
│   ├── lib/
│   │   ├── api.ts              # Centralized API client (/api/v1 prefix)
│   │   ├── types.ts            # Shared TypeScript types
│   │   └── utils.ts            # Utility functions
│   └── __tests__/              # Test files (vitest)
├── public/                     # Static assets
├── next.config.ts              # Next.js configuration
├── tailwind.config.ts          # Tailwind CSS configuration
└── tsconfig.json               # TypeScript configuration
```

---

## Key Libraries

| Library | Purpose |
|---------|---------|
| [next-intl](https://next-intl.dev/) | Internationalization (Hindi support) |
| [recharts](https://recharts.org/) | Chart visualizations |
| [react-force-graph](https://github.com/vasturiano/react-force-graph) | Citation graph visualization |
| [react-markdown](https://github.com/remarkjs/react-markdown) + remark-gfm | Markdown rendering in chat |
| [@testing-library/react](https://testing-library.com/) | Component testing |
| [vitest](https://vitest.dev/) | Test runner |

---

## Architecture

For detailed frontend architecture documentation, see [docs/FRONTEND_ARCHITECTURE.md](../docs/FRONTEND_ARCHITECTURE.md).
