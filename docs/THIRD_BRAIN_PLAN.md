# Third Brain — Plano de Execução (SaaS-ready, executando interno primeiro)

> Plano para evoluir o fork do `mindverse/Second-Me` (deployado em `meu.segundocerebro.ai`) em uma plataforma cognitiva. **Arquitetura SaaS-ready desde o dia 1**; **execução em modo interno multi-user** (você + time DocSales) até validarmos valor real; depois **launch público** sem refactor pesado.
>
> **Modo de execução:** você + Claude (vibe-coding), sprints semanais.

---

## 1. Contexto

### 1.1 De onde estamos partindo
- **Fork operacional:** [microsaasvb/segundocerebro](https://github.com/microsaasvb/segundocerebro) (Apache 2.0). Backend Flask em [lpm_kernel/](lpm_kernel/), frontend Next.js 14 em [lpm_frontend/](lpm_frontend/), deploy em Hetzner CPX31 (api.segundocerebro.ai) + Vercel (meu.segundocerebro.ai).
- **L0/L1/L2 funcionando:** SQLite ([docker/sqlite/init.sql](docker/sqlite/init.sql)) + ChromaDB + GraphRAG ([lpm_kernel/L1/](lpm_kernel/L1/)) + llama.cpp + treino LoRA via [lpm_kernel/L2/train_for_user.sh](lpm_kernel/L2/train_for_user.sh).
- **11 domínios Flask:** documents, health, kernel, kernel2, loads, memories, space, trainprocess, upload, user_llm_config (em [lpm_kernel/api/domains/](lpm_kernel/api/domains/)).
- **Hardcode crítico:** [load_service.py:67](lpm_kernel/api/domains/loads/load_service.py) "only one load record allowed". Toda query usa `.first()` sem scope.
- **Spec base:** [`third_brain_spec.md`](/Users/mauriciokigiela/Downloads/third_brain_spec.md).

### 1.2 Decisões já tomadas
| Decisão | Escolha |
|---|---|
| **Audiência** | Interno DocSales primeiro → SaaS público depois (validar valor antes de monetizar) |
| **Arquitetura** | SaaS-ready desde o início (multi-tenant verdadeiro, não single-tenant disfarçado) |
| **Time** | Você + Claude (vibe-coding), sprints semanais |
| **1º conector novo** | LLM History (ChatGPT/Claude/Gemini exports) |
| **LLM strategy** | Híbrido pragmático — Haiku/GPT-4o-mini para agentes, L2 local opcional |
| **Frontend host** | **Vercel** (mantém) |
| **Backend compute** | **Hetzner** (mantém — llama.cpp/Whisper/LLaVA/GraphRAG/L2 training local) |
| **DB + Auth + Storage + Realtime** | **Supabase** (Postgres + pgvector + Auth + Storage + RLS, região São Paulo) |
| **Workflow / background jobs** | **Hatchet** (Python-native, sem cross-language) |
| **Vector store** | **pgvector via Supabase** (substitui ChromaDB — uma DB só) |
| **File storage** | **Supabase Storage** (substitui filesystem local para uploads do usuário) |

### 1.3 Estratégia de duas fases
**Fase A — Validação interna (Sprints 0-15, ~16 semanas):**
- Arquitetura multi-tenant real (`tenant_id` em todas as tabelas).
- Sem signup público, sem billing, sem marketing site.
- Tenants criados por convite manual (allowlist em env var).
- Você + 3-5 do DocSales como early adopters.
- Métrica de sucesso: 80% das suas perguntas hoje multi-ferramenta passam a ser respondidas dentro do Third Brain.

**Fase B — Launch público SaaS (Sprints 16+, sob demanda):**
- Self-service signup (já que arquitetura está pronta).
- Billing (Stripe), plans/limits, trial.
- Marketing site, docs públicas, status page.
- DPA template, SOC2 readiness, sub-processor list.
- Onboarding self-service.

**Por que essa ordem importa:** se construirmos como single-tenant agora, refactor para multi-tenant depois é doloroso (Sprint inteiro de migração + risco de regressão). Construindo certo desde o início, "ligar" SaaS é só adicionar billing + signup, não reescrever core.

### 1.4 Resultado esperado (Fase A)
Ao final da Fase A:
1. Você (operador) usa diariamente; time DocSales (3-5 pessoas) tem tenants isolados.
2. 6 conectores ativos: LLM History, Gmail, Calendar, Drive, BeeMeet, WhatsApp.
3. 3 agentes proativos: Daily Briefing, Pre-meeting Briefing, Pattern Detection.
4. Auditoria queryável + LGPD checklist preenchido.
5. PT/EN cross-lingual funcional.
6. Cobertura de testes ≥70% nos services + connectors.
7. **Arquitetura pronta para Fase B** (sem dívida técnica que bloqueie launch SaaS).

---

## 2. Princípios (não-negociáveis)

| # | Princípio | Implicação |
|---|---|---|
| P1 | **SaaS-ready desde o dia 1** | `tenant_id` em toda tabela; auth OIDC pronta para externos; isolamento testado |
| P2 | **Local-first onde possível** | L0/L1/L2 e dados sensíveis ficam no servidor próprio. LLM externa só onde justifica |
| P3 | **Per-tenant logical isolation** em compute compartilhado | Schemas/collections/paths isolados por `tenant_id` |
| P4 | **Connectors são plugins** com contrato `BaseConnector` | Adicionar conector = 1 arquivo + migration |
| P5 | **Toda inferência cita fonte** (auditável) | Resposta de agente sempre aponta para evento L0/L1 |
| P6 | **Consent é dado de primeira classe** | Cada evento carrega `consent_level`, `training_eligible`, `pii_redacted_at` |
| P7 | **i18n: jamais traduzir no ingest** | Embeddings multilingual; idioma é metadata; resposta no idioma do query |
| P8 | **Vibe-coding friendly** | Mudanças incrementais, deploy contínuo, feature flags |

---

## 3. Arquitetura alvo

```
                ┌────────────────────────────────────┐
                │  Vercel (Next.js)                   │
                │  meu.segundocerebro.ai              │
                │  @supabase/auth-helpers-nextjs      │
                └──────────────┬─────────────────────┘
                               │ HTTPS
                  ┌────────────┴────────────┐
                  ↓                         ↓
       ┌────────────────────┐      ┌─────────────────────────┐
       │  Supabase (BR)     │      │  Hetzner CPX31           │
       │  ──────────────    │ ←SQL→│  api.segundocerebro.ai   │
       │  • Postgres 16     │      │  ──────────────────────  │
       │  • pgvector        │      │  • Flask API             │
       │  • Auth (OIDC+mag) │      │  • Hatchet workers       │
       │  • Storage (S3)    │      │  • llama.cpp / Whisper   │
       │  • Realtime        │      │  • LLaVA / GraphRAG      │
       │  • RLS por tenant  │      │  • L2 training (LoRA)    │
       │  • Vault (KEK)     │      │  • presidio (PII)        │
       └────────────────────┘      └────────────┬────────────┘
                                                ↑
                                                │ orquestra
                                    ┌───────────┴──────────┐
                                    │  Hatchet (Python)     │
                                    │  schedules/retries/   │
                                    │  fan-out/lineage      │
                                    └───────────────────────┘

Camadas funcionais:
┌──────────────────────────────────────────────────────────────────────┐
│  7 — Operator UI                                                      │
│  6 — Proactive Agents (Daily Briefing, Pre-meeting, Pattern, ...)    │
│  5 — LPM/L2 (fine-tuned por tenant — opcional)                       │
│  4 — L1 Knowledge Graph (GraphRAG, entity resolution)                │
│  3 — L0 Raw Storage (Postgres+pgvector tenant-isolated, RLS)         │
│  2 — Privacy & Consent (PII redaction, retention, erasure)           │
│  1 — Connector Hub                                                    │
│  0 — Auth (Supabase) + Tenant resolver                                │
└──────────────────────────────────────────────────────────────────────┘

Cross-cutting: Audit Trail (Postgres) | Sentry/OTel | Hatchet
Externos: Cloudflare, Resend (email), LiteLLM router → Anthropic/OpenAI/Ollama
```

### 3.1 Mudanças estruturais imediatas
- **DB:** SQLite local → **Supabase Postgres + pgvector** (região São Paulo). SQLite mantido apenas como modo dev local.
- **Vector store:** ChromaDB local → **pgvector na mesma Supabase**. Uma DB só, menos ops, backup automático.
- **File storage de usuário:** filesystem `/app/data/uploads/` → **Supabase Storage** (S3-compatible, signed URLs, CDN).
- **Modelos LLM e checkpoints L2:** continuam no Hetzner (4-8GB cada — caro/lento via Storage).
- **Auth:** zero → **Supabase Auth** (OIDC Google/GitHub + magic-link prontos; RLS nativo por `tenant_id`).
- **Background jobs:** sem queue → **Hatchet** (Python-native; durable execution, retries, schedules, fan-out, lineage). Self-host inicial em Hetzner ou Hatchet Cloud free tier.
- **Connector Hub:** novo módulo `lpm_kernel/connectors/` com `BaseConnector`, registry.
- **i18n:** `flask-babel` (backend) + `next-intl` (frontend); `language` em todo evento L0.
- **Audit:** `lpm_kernel/audit/` — append-only log no Postgres do Supabase, partitioned by month.
- **KEK por tenant** (envelope encryption): chave gerada na criação, persistida em **Supabase Vault** (Fase A) → KMS empresarial (Fase B).

### 3.2 Files críticos a modificar
| Arquivo | Mudança |
|---|---|
| [lpm_kernel/api/domains/loads/load_service.py:67](lpm_kernel/api/domains/loads/load_service.py) | Remover "only one load record"; `tenant_id` em queries |
| [lpm_kernel/common/repository/database_session.py](lpm_kernel/common/repository/database_session.py) | Supabase Postgres + `pgbouncer` connection pool |
| [docker/sqlite/init.sql](docker/sqlite/init.sql) | Reescrito como Alembic migrations + Supabase RLS policies por tabela |
| [lpm_kernel/api/services/embedding_service.py](lpm_kernel/api/services/embedding_service.py) | ChromaDB → **pgvector**; `search_similar` reescrito como SQL `<=>` query |
| [lpm_kernel/api/file_server/handler.py](lpm_kernel/api/file_server/handler.py) | Filesystem local → **Supabase Storage SDK** (upload/download/signed URLs) |
| [lpm_kernel/L1/l1_generator.py](lpm_kernel/L1/l1_generator.py) | Aceitar `tenant_id`; output isolado; tasks via Hatchet workflows |
| [lpm_kernel/L2/train_for_user.sh](lpm_kernel/L2/train_for_user.sh) | Aceitar `--tenant-id`; output `/app/resources/{tenant_id}/model/output/` (fica no Hetzner) |
| [lpm_kernel/api/__init__.py](lpm_kernel/api/__init__.py) | Middleware Supabase JWT verifier + tenant resolver + audit logger |
| [lpm_frontend/src/utils/request.ts](lpm_frontend/src/utils/request.ts) | Substituir auth manual por `@supabase/auth-helpers-nextjs` + injetar JWT |
| **Novo** `lpm_kernel/jobs/` | Hatchet workflows (ingestão, indexing, agents, training) |
| **Novo** `lpm_kernel/storage/` | Wrapper Supabase Storage |
| **Novo** `lpm_kernel/auth/supabase.py` | Verificação de JWT do Supabase, resolução de tenant |

---

## 4. Sprints (semanais)

> 1 sprint = 1 semana. Você executa, Claude implementa. Deploy contínuo.

### Sprint 0 — Foundations (semana 1)
**Objetivo:** estancar dívida técnica antes de adicionar features.
- Branch `third-brain` no repo.
- GitHub Actions CI: lint (ruff + ESLint) + pytest + build Docker.
- **Provisionar projeto Supabase** (região São Paulo): habilitar `pgvector` extension, criar bucket `uploads`, configurar Auth providers (Google OIDC + magic-link).
- Alembic configurado contra Supabase Postgres; primeira migration espelha schema atual + adiciona `tenants` + `tenant_users` tables (`users` vem da `auth.users` do Supabase).
- **Hatchet** instalado (Hatchet Cloud free tier ou self-host em container Hetzner). Worker skeleton + task `health_check` rodando.
- Migrar bucket lógico de uploads para Supabase Storage (paridade com filesystem atual).
- Pytest configurado: `tests/unit/`, `tests/integration/`, `tests/e2e/`. Coverage gate em 50%.
- Sentry (backend + frontend) + OpenTelemetry traces.
- Pre-commit hooks (`ruff`, `mypy` em `lpm_kernel/api/`).
- **Verificação:** staging.segundocerebro.ai conecta no Supabase, Hatchet worker healthy, sem regressão funcional.

### Sprint 1 — Auth + tenant foundation (semana 2) — *Epic Multi-Tenant*
- **Supabase Auth** ativo: Google OIDC + magic-link (configurado no painel Supabase, sem código de auth próprio).
- Tabela `tenants` (id, slug, display_name, region, kek_id, plan, status).
- Tabela `tenant_users` (tenant_id, user_id, role) — `user_id` referencia `auth.users.id` do Supabase.
- **JWT do Supabase** carrega claim customizada `tenant_id` (via Supabase Hook `custom_access_token_hook`). Backend só verifica assinatura.
- Middleware Flask `@require_tenant`: valida JWT do Supabase via JWKS, injeta `g.tenant_id`, `g.user_id`, `g.role`.
- Frontend: `@supabase/auth-helpers-nextjs` substitui auth manual; tela de login + tenant switcher se user pertence a múltiplos.
- **Allowlist na Supabase** (`auth.users` + RLS) — sem signup público na Fase A. Convite via comando admin `python -m lpm_kernel.admin invite_user --email=... --tenant-slug=...` que chama `supabase.auth.admin.invite_user_by_email()`.
- Testes: middleware (JWT válido/expirado/inválido/cross-tenant) + Playwright e2e do login com Supabase test client.

### Sprint 2 — Tenant data isolation + ChromaDB→pgvector (semana 3) — *Epic Multi-Tenant*
- Migration: `tenant_id UUID NOT NULL REFERENCES tenants(id)` em `documents`, `chunks`, `l1_*`, `memories`, `roles`, `user_llm_configs`, `loads`, `spaces`.
- **Supabase RLS policies por tabela** como camada primária de isolamento (`USING (tenant_id = (auth.jwt()->>'tenant_id')::uuid)`).
- SQLAlchemy: query mixin como camada secundária (defense-in-depth).
- Backfill: tudo existente vira do tenant default (`docsales`).
- Remover hardcode "only one load record" em [load_service.py:67](lpm_kernel/api/domains/loads/load_service.py).
- **Migração ChromaDB → pgvector**:
  - Adicionar coluna `embedding vector(1536)` (ou dimensão do modelo) em `chunks`.
  - Script 1-shot que lê ChromaDB, insere embeddings em pgvector, valida contagem.
  - Reescrever `embedding_service.search_similar()` para SQL `ORDER BY embedding <=> :query LIMIT k`.
  - Index HNSW: `CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)`.
  - Desligar ChromaDB depois de validar paridade de resultados.
- **Migração filesystem → Supabase Storage** (uploads de usuário; modelos LLM ficam no Hetzner).
  - Bucket `uploads` com path `{tenant_id}/{document_id}/{filename}`.
  - RLS policy: user só lê/escreve seu próprio tenant.
- KEK por tenant: gerada na criação, persistida em **Supabase Vault**, usada para cifrar `connectors.config_encrypted`.
- **Teste de isolamento:** 3 tenants, popular cada, validar zero cross-tenant leak em 50 endpoints + bypass tentativo via JWT manipulado.
- Audit: cada query/mutação loga `(tenant_id, user_id, action, resource, ts)`.

### Sprint 3 — Connector Hub + LLM History (semana 4) — **Quick win #1**
- Módulo `lpm_kernel/connectors/base.py` com `BaseConnector` ABC + `CanonicalEvent` Pydantic model.
- Registry pattern + auto-discovery.
- Tabela `connectors` (id, tenant_id, type, status, config_encrypted, last_sync_at, error_count).
- Hatchet workflows padrão: `connector.backfill`, `connector.process_event`.
- **Conector LLM History v1:**
  - `ChatGPTHistoryConnector`: parser do export ZIP (`conversations.json`).
  - `ClaudeHistoryConnector`: parser do export oficial (`conversations.json`).
  - `GeminiHistoryConnector`: parser do Google Takeout.
  - Cada conversa vira sessão em L0; L1 extrai tópicos/decisões/padrões; L2 (se ativo) aprende estilo.
- UI: tela "Connectors" com upload de export ZIP, status, last sync.
- **Verificação:** suba seus exports reais. Pergunte "o que conversamos sobre Third Brain?" e valide retorno relevante com fontes citadas.

### Sprint 4 — Privacy & Consent Engine (semana 5) — *Epic Privacy*
- Tabela `consent_policies` por tenant + `entity_consent_map` (pessoa → flag training_eligible, retention_days).
- PII redactor: `presidio` (Microsoft) com analyzers PT-BR + EN. Detecta CPF, RG, cartão, telefone, email, chaves API. Substitui por tokens `<PII:CPF:hash>`.
- Pipeline L0 → L1 passa por redactor.
- Endpoint `DELETE /api/privacy/erase?subject=<email|phone>` purga cross-tabela + marca L2 retraining.
- Retention enforcer: Hatchet schedule nightly purge expirados.
- DSAR export: ZIP com tudo de um identificador.
- Testes: evento com CPF → L1 contém token; erasure → cross-tabela limpa.

### Sprint 5 — Gmail + Calendar + Contacts (semana 6) — **Quick win #2**
- `GmailConnector`: OAuth Google, `history.list` incremental, threads + labels.
- `GoogleCalendarConnector`: events + RSVP.
- `GoogleContactsConnector`: People API; alimenta entity resolution L1.
- Anexos roteados ao DriveConnector (Sprint 7).
- Classificação automática `professional|personal` por domínio.
- Testes: mock OAuth callback + fixtures Gmail.
- **Verificação:** conecte sua conta. Daily briefing começa a fazer sentido.

### Sprint 6 — Daily Briefing Agent (semana 7) — **Quick win #3**
- `DailyBriefingAgent`: Hatchet schedule (cron `0 6 * * *` no timezone do tenant). Query L1 últimas 24h → LLM (Haiku/4o-mini) → push notification + email (Resend).
- Tabela `agent_runs` (audit): `agent_name, tenant_id, started_at, finished_at, status, output, tokens_consumed, cost_usd`.
- UI: feed de "insights" no dashboard.
- **Verificação:** receba seu primeiro briefing PT-BR às 06:00.

### Sprint 7 — Drive + Dropbox + OneDrive (semana 8)
- `GoogleDriveConnector` (changes API), `DropboxConnector` (cursor), `OneDriveConnector` (Graph delta).
- Apenas metadata + texto extraído por default.
- OCR via Tesseract; PDFs via pdfplumber; Office via python-docx/openpyxl/python-pptx.
- Testes: fixtures de cada fonte.

### Sprint 8 — BeeMeet + Twilio + manual transcripts (semana 9)
- `BeeMeetConnector`: webhook beemeet.ai → ingere transcript + speakers diarizados.
- `TwilioVoiceConnector`: webhook de chamadas, gravação, Whisper, diarização pyannote.
- `ManualTranscriptConnector`: upload de Otter, Fireflies, Krisp, Granola.
- Consent UX: arquivo carrega `consent_level: pending` até user marcar speakers.
- Testes: fixtures PT + EN; valida transcrição + diarização + redaction.

### Sprint 9 — WhatsApp via Evolution API (semana 10)
- Deploy próprio do Evolution API em VPS pequeno separado.
- `WhatsAppConnector`: webhook receiver + Hatchet workflow `process_event`.
- Backfill via export ZIP (chat-by-chat).
- Mídia: áudio → Whisper, imagem → LLaVA via Ollama, PDF → pdfplumber.
- Detecção de idioma por mensagem.
- UI: conectar via QR code; toggles individuais por grupo (consent).
- **Risco documentado:** Evolution API é WhatsApp Web não-oficial; bloqueio possível. Best-effort.
- Testes: integration + fim-a-fim mock.

### Sprint 10 — Pre-meeting Briefing + Pattern Detection (semana 11)
- `PreMeetingBriefingAgent`: trigger 30min antes de evento. Dossier de participantes.
- `PatternDetectionAgent`: nightly. Tópicos repetidos, contatos esfriando, padrões.
- UI: alertas push + email.

### Sprint 11 — Operator UI completa (semana 12)
- **Dashboard**: briefing do dia, inbox unificada, próximos eventos, alertas.
- **Timeline**: cronologia reversa, filtros (pessoa/projeto/tópico/fonte/sentiment), drill-down até L0.
- **People view**: ranqueado por relevância, timeline por pessoa.
- **Project view**: detectados em L1, decisões + docs + status.
- **Chat com LPM**: comandos `/briefing`, `/sobre [pessoa]`, `/projeto [nome]`, `/decisões pendentes`. Sempre cita fonte.
- Testes: Playwright e2e top 10 jornadas.

### Sprint 12 — i18n epic (semana 13) — *Epic Multi-Language*
- **Backend**: `flask-babel` + extração. Iniciais: pt-BR, en-US.
- **Frontend**: `next-intl` substituindo strings hardcoded. `messages/{pt-BR,en-US}.json`.
- **Embeddings multilingual**: trocar default para BGE-M3. Migration tooling para reindexar.
- **LLM prompts** parametrizados por idioma do query.
- **ASR**: Whisper large-v3, detecção por chunk (code-switching).
- **Persistência**: campo `language` em todo evento L0.
- **Eval gate** no CI: recall@k por par (PT→PT, PT→EN, EN→PT, EN→EN).
- Testes: dataset cross-lingual.

### Sprint 13 — Audit & observability hardening (semana 14)
- Tabela `audit_log` append-only partitioned by month.
- Decorator `@audit("action_name")` em todo serviço de mutação.
- Cada inferência LLM loga: prompt template, fontes citadas (L0/L1 ids), modelo, tokens, custo, latência.
- Dashboard interno (Grafana + Prometheus): ingestão, latência, erro por conector, custo, recall@k.
- Auditor agent (`AuditAgent`): nightly varre `audit_log` procurando padrões anômalos.
- Cost auditor: alerta por tenant budget.
- Pen-test interno (OWASP top 10 + cross-tenant access).

### Sprint 14 — Decision Tracker + Relationship Health (semana 15)
- `DecisionTrackerAgent`: detecta "vamos seguir com X", "decidimos Y" → marca em L1, alerta inconsistências.
- `RelationshipHealthAgent`: monitora cadência com pessoas-chave, alerta gaps.

### Sprint 15 — L2 multi-tenant opcional (semana 16)
- [train_for_user.sh](lpm_kernel/L2/train_for_user.sh) aceita `--tenant-id`; output isolado.
- Job orchestrator: nightly por tenant, fila local com 1 GPU.
- A/B framework: ganho L2 vs base+RAG por tenant. Ativa automaticamente se score > threshold.
- Catastrophic forgetting check: smoke test pós-train.

### **🚀 Marco: fim da Fase A (validação interna)**

**Decisão:** ir para Fase B (launch público) ou continuar otimizando interno? Critérios:
- Você usa diariamente (>5 vezes/dia)?
- Time DocSales tem NPS > 7?
- 80% das perguntas multi-ferramenta resolvidas dentro do Third Brain?

---

### Fase B — Launch público SaaS (Sprints 16+)

### Sprint 16 — Self-service signup (semana 17)
- Endpoint público `POST /api/auth/signup` cria tenant + user owner em transação.
- Fluxo de email verification.
- Onboarding wizard: cria primeiro connector (LLM History recomendado).
- Trial de 14 dias (feature flag).

### Sprint 17 — Billing (Stripe) (semana 18)
- Plans: Free (limitado), Pro (mensal), Enterprise (custom).
- Stripe Checkout + webhooks.
- Tabela `subscriptions`; gates por feature/quota.
- CostAuditor já existente conecta com gates de plan.

### Sprint 18 — Marketing site + docs (semana 19)
- Landing page (next.js, route separada).
- Docs públicas (Mintlify ou Nextra).
- Status page (BetterStack ou statuspage.io).

### Sprint 19 — Compliance enterprise (semana 20)
- DPA template público.
- Sub-processor list página `/legal/subprocessors`.
- SOC2 Type 1 readiness assessment (Vanta ou Drata).
- Data residency real (BR/EU regions).

### Sprint 20+ — Roadmap aberto (Fase B)
- Crisis Detection Agent.
- Mobile recorders nativos (iOS/Android/macOS).
- Marketplace de connectors (terceiros publicam plugins).
- Cloud LLM router com fallback inteligente.
- Captura de tela desktop (Electron).
- LinkedIn/Twitter/Slack connectors.

---

## 5. Epics em paralelo

| Epic | Sprints | Status |
|---|---|---|
| **E1: Multi-Tenant Foundation** | S1, S2, depois cross-cutting | **Crítico** — SaaS-ready desde dia 1 |
| **E2: Multi-Language (i18n)** | S12, polimento contínuo | Importante |
| **E3: Connector Hub** | S3, S5, S7, S8, S9 | Core feature |
| **E4: Proactive Agents** | S6, S10, S14 | Diferenciação |
| **E5: Privacy/LGPD/GDPR** | S4, contínuo | Compliance |
| **E6: Audit & Observability** | S13, hooks desde S0 | Operacional |
| **E7: Tests & Quality** | Cross-cutting desde S0 | Sustentável |
| **E8: Operator UI** | S11, polimento contínuo | UX |
| **E9: L2/LPM** | S15+ | Premium |
| **E10: SaaS Plumbing** | S16-S19 | Fase B |

---

## 6. Epic E1 — Multi-Tenant Foundation (detalhado)

### 6.1 Modelo
**Hybrid: shared compute + per-tenant logical isolation** (padrão SaaS moderno):
- 1 deploy backend, N tenants.
- Postgres com `tenant_id` em toda tabela + RLS opcional como 2ª camada.
- ChromaDB: 1 collection por (tenant, kind). Naming: `chunks_{tenant_uuid}`, `docs_{tenant_uuid}`.
- Filesystem: paths prefixados `{base}/{tenant_uuid}/...`.
- **KEK por tenant**: chave gerada na criação. Fase A persiste em env var cifrada (suficiente para uso interno). Fase B migra para Hetzner Vault ou AWS KMS.
- **Tenant pode ter N users** (DocSales tenant tem você + 3-5 do time).
- **User pode pertencer a múltiplos tenants** (consultor que atende vários clientes).

### 6.2 Schema novo
```sql
CREATE TABLE tenants (
  id UUID PRIMARY KEY,
  slug VARCHAR(64) UNIQUE NOT NULL,
  display_name VARCHAR(255) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  region VARCHAR(16) NOT NULL DEFAULT 'br',  -- data residency
  kek_id VARCHAR(255) NOT NULL,
  plan VARCHAR(32) NOT NULL DEFAULT 'internal',  -- internal | free | pro | enterprise
  status VARCHAR(32) NOT NULL DEFAULT 'active'
);
CREATE TABLE users (
  id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  full_name VARCHAR(255),
  oidc_subject VARCHAR(255) UNIQUE,
  language_preference VARCHAR(8) DEFAULT 'pt-BR',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE tenant_users (
  tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(32) NOT NULL CHECK (role IN ('owner','admin','member','viewer')),
  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (tenant_id, user_id)
);
```

### 6.3 Padrões obrigatórios
- **Camada primária**: Supabase RLS policies em toda tabela de domínio.
- **Camada secundária**: SQLAlchemy mixin que injeta `WHERE tenant_id = :tenant_id` (defense-in-depth).
- Toda Hatchet task recebe `tenant_id` como primeiro argumento do payload.
- Toda inserção: `tenant_id = g.tenant_id` injetado pelo middleware.
- Cross-tenant query: APENAS via endpoint admin `super_admin` usando service-role JWT, com auditoria reforçada.

### 6.4 Critério de aceitação
**Teste de penetração:** crie tenant A com 100 docs, tenant B com 0 docs. Login como B, executa 50 queries variadas (search, list, agent). **Zero docs de A retornados** em qualquer endpoint. Repete teste após cada sprint.

---

## 7. Epic E2 — Multi-Language (detalhado)

### 7.1 Camadas
| Camada | Estratégia |
|---|---|
| **UI strings** | `next-intl` (frontend) + `flask-babel` (backend). Locale em `users.language_preference`. |
| **Embeddings** | BGE-M3 multilingual (default). Mesma collection serve PT+EN. |
| **ASR** | Whisper large-v3, detecção por chunk. |
| **Conteúdo armazenado** | Original sempre. Campo `language ISO 639-1` em metadata. NUNCA traduzir no ingest. |
| **Resposta LLM** | Detecta idioma do query → instrui modelo a responder no idioma do query, citando fonte no idioma original. |
| **Datas/números** | `Intl` no frontend, `babel.dates`/`babel.numbers` no backend. |

### 7.2 Eval gate
Dataset de 50 queries × 4 pares (PT→PT, PT→EN, EN→PT, EN→EN). CI bloqueia merge se recall@5 cai > 5pp em qualquer par.

### 7.3 Idiomas
- v1: pt-BR, en-US (S12).
- v2 (Fase B sob demanda): es-ES, fr-FR, de-DE.

### 7.4 Critério de aceitação
User PT abre app em pt-BR, ingere email em EN com decisão "we will go with vendor X", pergunta "qual fornecedor decidimos?", recebe resposta em PT-BR citando o email original em EN.

---

## 8. Epic E3 — Connector Hub (contratos)

```python
# lpm_kernel/connectors/base.py
class BaseConnector(ABC):
    type: str              # "llm_history_chatgpt", "gmail", "whatsapp"...
    config_schema: type[BaseModel]

    @abstractmethod
    def health(self) -> ConnectorHealth: ...
    @abstractmethod
    def backfill(self, since: datetime) -> Iterator[CanonicalEvent]: ...
    @abstractmethod
    def normalize(self, raw: dict) -> CanonicalEvent: ...

    # Optional
    def stream(self) -> Iterator[CanonicalEvent]: ...
    def poll(self) -> Iterator[CanonicalEvent]: ...

class CanonicalEvent(BaseModel):
    tenant_id: UUID
    source_connector: str
    source_id: str          # idempotency key
    occurred_at: datetime
    participants: list[ParticipantRef]
    content: str
    mime_type: str
    language: str | None
    consent_level: Literal["explicit","implicit","ambient","third_party"]
    raw_payload_uri: str
    metadata: dict
```

Conectores priorizados (ordem de entrega):
1. **LLM History** (S3) — ChatGPT + Claude + Gemini exports
2. **Gmail + Calendar + Contacts** (S5)
3. **Drive + Dropbox + OneDrive** (S7)
4. **BeeMeet + Twilio + Manual Transcripts** (S8)
5. **WhatsApp via Evolution** (S9)

Postergados (Fase B):
- Mobile recorders (iOS/Android/macOS apps próprios)
- Captura de tela desktop (Electron)
- LinkedIn/Twitter/Slack
- Marketplace de connectors de terceiros

---

## 9. Epic E5 — Privacy & Consent (LGPD/GDPR)

### 9.1 Controles obrigatórios
- **Base legal explícita** por fonte (art. 7º LGPD / art. 6 GDPR).
- **Consent map por entidade**: pessoa identificada → flag `training_eligible`. Pessoas marcadas "no train" têm conteúdo em L0 mas excluído de L2.
- **PII redaction** automática (presidio + custom recognizers PT-BR).
- **Retention TTL** por fonte (configurável): voz ambiente 30d, email 1 ano, decisões 5 anos.
- **Right to erasure**: endpoint que aceita identificador → purge cross-tabela + retraining marcado.
- **DSAR export**: ZIP com tudo de um identificador.
- **Audit log de todo acesso a dados de terceiros**.
- **Data residency** respeita `tenants.region` (Fase B).

### 9.2 Guardrails de execução (runtime)
| Guardrail | Implementação |
|---|---|
| **PII em LLM externa** | Pré-processador substitui PII por tokens antes de enviar; pós-processador re-injeta na resposta para o operador |
| **Training set sem PII de terceiros** | Job de geração L2 filtra eventos `consent_level in ('ambient','third_party')` salvo whitelist |
| **Voz sem speaker identificado** | Auto-anonimização antes de L1 |
| **Limite de retenção** | Hatchet schedule nightly purge eventos expirados |
| **Rate limit por tenant** | Evita custo descontrolado |

### 9.3 Critério de aceitação Fase A
- Checklist LGPD preenchido (template ANPD).
- Erasure end-to-end funciona (purge L0 + L1 + ChromaDB + filesystem).
- DSAR export gera ZIP legível.

### 9.4 Critério Fase B (launch público)
- Auditor externo (advogado LGPD) revisa fluxo: ≤5 issues médias, zero high.
- DPA template público.
- SOC2 Type 1 em andamento.

---

## 10. Epic E6 — Auditoria & Observabilidade

### 10.1 Audit log
Toda ação que muda estado escreve em `audit_log` (append-only, partitioned by month):
```
ts | tenant_id | user_id | actor_type (user|agent|system|connector) |
action | resource_type | resource_id | before_hash | after_hash |
ip | user_agent | request_id | tokens_used | cost_usd
```

### 10.2 Auditores de execução (agentes)
- **AuditAgent**: nightly varre padrões anômalos (ação fora de horário, volume atípico, cross-tenant attempt).
- **CostAuditor**: agrega custo de LLM por tenant; alerta orçamento.
- **DataLineage**: dado output de agente, retorna árvore de fontes (L0 ids → L1 nodes → LLM prompt). Endpoint `/api/audit/lineage/<inference_id>`.

### 10.3 Observabilidade
- **OpenTelemetry**: traces backend → frontend.
- **Sentry**: exceções runtime.
- **Grafana + Prometheus**: dashboards de ingestão, latência, erro por conector, custo, recall@k.
- **Health endpoints** por componente.

---

## 11. Epic E7 — Estratégia de testes

### 11.1 Pirâmide
| Tipo | Cobertura alvo | Ferramenta | Quando |
|---|---|---|---|
| **Unit** | 70% nos services + repositories | pytest + pytest-mock | Pre-commit + CI |
| **Integration** | Fluxos por domínio | pytest + Supabase local (`supabase start`) | CI |
| **Contract (connectors)** | 100% dos `BaseConnector` filhos | pytest fixtures de payload | CI |
| **Tenant Isolation** | Cross-tenant access checks (RLS + mixin) | Custom suite executada após cada migration | CI |
| **E2E** | Top 10 jornadas | Playwright + Supabase test client | CI nightly + pre-release |
| **Eval (LLM/RAG)** | Recall@k por idioma, hallucination | promptfoo ou ragas | CI nightly |
| **Security** | OWASP top 10 + RLS bypass tentativas | bandit, safety, custom pytest | CI weekly |

### 11.2 Coverage gate
Sprint 0: 50%. Sobe 5pp/sprint até 70% global, 85% em `lpm_kernel/api/services/` e `lpm_kernel/connectors/`.

### 11.3 Test data
Fixtures sintéticas via Faker; **dados reais nunca no repo**. Para E2E: tenant `test_tenant` populado por seed Hatchet workflow no setup.

---

## 12. Stack & dependências novas

| Categoria | Escolha | Justificativa |
|---|---|---|
| **Frontend host** | Vercel | Já em produção; Next.js nativo |
| **Backend compute** | Hetzner CPX31 (escalável) | llama.cpp/Whisper/LLaVA/GraphRAG/L2 training local |
| **DB + Auth + Storage** | Supabase (região São Paulo) | Postgres + pgvector + Auth + Storage + RLS + Vault em um lugar; LGPD-friendly |
| **Vector store** | pgvector (no Supabase) | Substitui ChromaDB; uma DB só |
| **Storage de upload** | Supabase Storage | S3-compatible, signed URLs, CDN, RLS por tenant |
| **Queue / orquestração** | **Hatchet** (Python-native) | Durable execution, retries, schedules, fan-out, lineage. Sem cross-language |
| **Auth** | Supabase Auth (Google OIDC + magic-link) | Pronto, RLS nativo, JWT JWKS |
| **Email transacional** | Resend | Magic-link templates customizáveis |
| **Migrations** | Alembic | Padrão SQLAlchemy |
| **PII** | presidio (Microsoft) | Multi-idioma; recognizers PT-BR adicionáveis |
| **LLM router** | LiteLLM | Swap Anthropic/OpenAI/Ollama/llama.cpp trivial |
| **Embedding** | BGE-M3 (local) ou OpenAI text-embedding-3-large | Multilingual PT/EN cross-lingual |
| **ASR** | Whisper large-v3 (local) | PT excelente; detecção de idioma per chunk |
| **Diarização** | pyannote | Open source; precisão decente |
| **CDN + DNS + WAF** | Cloudflare | Já configurado |
| **Observabilidade** | Sentry + OpenTelemetry + Hatchet UI + Supabase logs | OSS + nativo de cada stack |
| **Métricas custom** | Grafana + Prometheus (opcional, sob demanda) | Quando dashboards Hatchet/Supabase não bastarem |
| **Testes** | pytest + Playwright + Supabase local + promptfoo | Padrão moderno |
| **Frontend i18n** | next-intl | Padrão App Router |
| **Backend i18n** | flask-babel | Padrão Flask |
| **Secrets** | Supabase Vault (Fase A) → AWS Secrets Manager (Fase B) | KEK por tenant + creds de connectors |
| **Billing (Fase B)** | Stripe | Standard SaaS |

### 12.1 Custos estimados Fase A (interna, ~5 tenants)
| Item | Custo/mês |
|---|---|
| Hetzner CPX31 (4 vCPU, 8GB) | ~€10 |
| Supabase Pro (8GB DB, 100GB Storage incluso) | $25 |
| Vercel Pro (já tem) | já pago |
| Hatchet Cloud free tier (até 1000 runs/mês) ou self-host | $0 |
| Resend (até 3000 emails/mês) | $0 |
| Cloudflare | $0 |
| LLM API (Haiku/4o-mini, ~5 users moderados) | ~$30-80 |
| **Total estimado** | **~$80-130/mês** |

### 12.2 Custos extras Fase B (launch público)
- Stripe: 2.9% + $0.30 por transação.
- Hatchet Cloud paid (~$30/mês) ou cluster maior se self-host.
- Supabase Team plan ($599/mês) se ultrapassar limites Pro.
- SOC2 (Vanta/Drata): $5-15k/ano.

---

## 13. Decisões pendentes

**Durante Fase A (resolver no sprint indicado):**
1. **Embedding provider quando crescer:** BGE-M3 local vs Cohere multilingual vs OpenAI? Decidir em S3 com benchmark.
2. **Modelo LLM para agentes:** Claude Haiku 3.5 vs GPT-4o-mini? Decidir em S6 com benchmark.
3. **WhatsApp Evolution self-host vs serviço gerenciado** (UAZAPI etc): decidir em S9.
4. **L2 fine-tuning compensa para uso interno?** A/B em S15.

**Antes da Fase B:**
5. Open-source da Third Brain layer ou proprietária?
6. Pricing model: per-seat? per-storage? per-LLM-token?
7. Marketing/positioning: "AI second brain LATAM" ou genérico?
8. Mobile apps: build próprio ou parceria com Otter/Granola/etc?

---

## 14. Riscos e mitigações

| Risco | Prob | Impacto | Mitigação |
|---|---|---|---|
| Bloqueio Evolution API pelo Meta | Média | Alta | Best-effort + fallback export manual; migrar para WA Business API quando justificar |
| LGPD/GDPR sobre voz ambiente | Alta | Alta | Default OFF; integração via wearables visíveis; redação automática; opt-in explícito |
| Hardware Hetzner insuficiente para L2 multi-tenant | Média | Média | MVP roda com base+RAG; L2 opcional; upgrade para CCX33 (32GB) ou cloud burst se justificar |
| Second-Me upstream diverge | Alta | Média | Manter contribuições upstream em L0/L1/L2 core; Third Brain como camadas acima |
| Custo LLM API explode | Média | Alta | CostAuditor + budget gates por tenant; modelos baratos para tasks simples |
| Cross-tenant data leak | Baixa | **Crítica** | Testes automatizados + RLS Postgres + pen-test trimestral |
| Catastrophic forgetting em retraining | Média | Média | Smoke test pós-train; rollback automático |
| Adoção interna fraca | Média | Alta | LLM history como onboarding instantâneo; demos semanais nas 4 primeiras semanas |
| Multilíngue degrada cross-lingual recall | Média | Média | CI gate em recall@k por par |
| Vibe-coding gera dívida técnica | Alta | Média | Coverage gate crescente; refactor sprint a cada 4 sprints |
| Demora em decidir launch (Fase B) | Média | Baixa | Marco claro após S15; critérios objetivos para go/no-go |

---

## 15. Verificação end-to-end

### 15.1 Fim da Fase A (interna DocSales)
1. **Multi-tenant:** 5 tenants isolados; pen-test confirma zero vazamento.
2. **Multi-idioma:** demo PT, demo EN, query cross-lingual funcional.
3. **6 conectores ativos:** LLM History + Gmail + Calendar + Drive + BeeMeet + WhatsApp sincronizando.
4. **3 agentes proativos** rodando: Daily Briefing, Pre-meeting, Pattern Detection.
5. **Privacy:** checklist LGPD assinado; DSAR + erasure funcionam.
6. **Audit:** lineage de qualquer output funciona.
7. **Testes:** ≥70% coverage global, ≥85% em services + connectors. Suite e2e verde.
8. **Observabilidade:** Grafana com métricas; alertas configurados.
9. **Documentação:** README de cada conector, runbook de incidentes.
10. **Métrica de valor:** você usa diariamente; NPS time DocSales > 7.

### 15.2 Fim da Fase B (launch público)
11. Self-service signup funcional.
12. Stripe integrado; primeiro pagamento real recebido.
13. Marketing site live; status page público.
14. DPA template + sub-processor list públicos.
15. SOC2 Type 1 readiness em andamento.
16. Primeiros 10 paying customers.

---

## 16. Próximos passos imediatos (após aprovação)

1. **Sprint 0 começa esta semana.**
2. Criar branch `third-brain` no repo.
3. Provisionar Supabase (BR) + Hatchet (Cloud free tier) + conexão do Hetzner.
4. CI GitHub Actions configurado.
5. Demo interna toda sexta-feira.
6. Revisão de roadmap a cada 4 sprints.
7. Decisão Fase A → Fase B no Sprint 16 (~mês 4).

---

> **Tempo total estimado** (vibe-coding, você + Claude):
> - **Fase A** (validação interna): ~16 semanas (~4 meses) até MVP completo (S15).
> - **Quick wins** (LLM History + Daily Briefing): chegam em 7 semanas.
> - **Fase B** (launch SaaS): +4-6 semanas (S16-S20+) **se** decidirmos avançar.
