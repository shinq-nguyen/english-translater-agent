# AGENTS.md — EN Translator for IT

This repo is a demo target for Codex Session 2 (MCP, Skills vs Subagents,
Exec Policy & Hooks). It is a real, runnable Spring Boot + React app, not a
toy — that's the point: the workshop demos show these mechanisms against
code with actual secrets, a real database, and real architectural seams.

## What this app is

A web app that helps Vietnamese IT professionals translate/polish text into
professional English, with AI-powered grammar feedback. Backend: Java 21 /
Spring Boot 3.3 / Postgres 16 / Flyway. Frontend: React 19 / TypeScript /
Vite.

## Where things live

- `backend/src/main/java/com/example/translator/translation/` — the
  provider-agnostic translation pipeline. `AiProviderClient` is the
  interface each AI provider implements; `AiProviderClientRegistry` looks up
  the right client by `AiProviderType`; `AnthropicProviderClient` and
  `OpenAiCompatibleProviderClient` are the two existing implementations.
- `backend/src/main/java/com/example/translator/aimodel/` — admin-managed
  AI model configs. `AiProviderType` is the provider enum.
  `ApiKeyAttributeConverter` transparently AES-256-GCM encrypts/decrypts the
  stored API key using `AI_MODEL_ENCRYPTION_KEY`.
- `backend/src/main/java/com/example/translator/auth/`,
  `.../security/` — JWT auth, signed with `APP_JWT_SECRET`.
- `backend/src/main/resources/db/migration/` — Flyway SQL migrations
  (source of truth for the schema — this is what the MCP Postgres server
  will expose).
- `.env` (git-ignored, copy from `.env.example`) holds both secrets above in
  plaintext for local `docker compose` runs. Treat it as sensitive: never
  cat/print it, never put its contents in a commit, PR description, or
  chat.

## Working in this repo

- Backend tests: `cd backend && mvn test`.
- Full stack: `docker compose up -d --build` (needs `.env` — see
  `.env.example`).
- Don't invent a new secrets-storage mechanism; reuse
  `ApiKeyAttributeConverter`'s pattern if a new provider needs a stored
  credential.

## Demo config in this repo

This checkout intentionally ships `.codex/` and `.agents/` configuration
used by the Session 2 demos: an MCP server pointed at the local Postgres, a
`secret_auditor` subagent, an `add-ai-provider` skill, exec-policy rules,
and a couple of lifecycle hooks. See `demo-material/00-setup.md` (machine
setup, do this first) and `demo-material/01-overview.md` (what each piece is
for and how to try it yourself).
