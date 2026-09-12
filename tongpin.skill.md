---
name: tongpin
description: "Run, inspect, or demonstrate Tongpin/同频 from its repository, including Codespaces or local startup, the onboarding-to-outcome workflow, API smoke tests, recommendation explanations, consent, privacy, and safety behavior. Use only when the request explicitly names Tongpin/同频 or this repository's web product; do not use for generic dating advice or unrelated FastAPI/Next.js work."
metadata:
  short-description: "Run and operate the Tongpin product"
---

# Tongpin

Use this skill to operate the actual product in this repository, not a paper walkthrough. The deliverable is a running FastAPI + Next.js application backed by the repository's tests and data contracts.

## Locate the repository

1. Prefer the current workspace if it contains `apps/web`, `services/backend`, and `docs/matching-metrics-v0.1.md`.
2. If the skill is installed globally, ask for a local checkout path. The public repository is `https://github.com/selene4441-cmd/Soul-Mate.git`; clone it only with permission.
3. Treat the repository root as the working directory for startup and verification commands.

## Choose the operating mode

### Start or demonstrate

Use for requests such as “启动同频”, “带我体验完整流程”, or “run Tongpin”.

1. For a shareable remote environment, direct the user to `https://codespaces.new/selene4441-cmd/Soul-Mate` and use forwarded port `3000`.
2. For a local machine, use the repository launcher:
   - Windows: `powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1`
   - macOS/Linux/Git Bash: `bash scripts/start-local.sh`
3. Wait for the API health check at `http://127.0.0.1:8000/api/v1/health` and the web app at `http://127.0.0.1:3000`.
4. Drive the real UI: register, grant the requested consent scopes, complete the scenario questionnaire, correct Claims, generate relationship leads, invite, exchange messages, and submit outcome feedback.
5. If the user only asks to launch the product, stop after confirming both health checks. Do not create accounts, send invitations, or modify data unless requested.

### Inspect or change product behavior

Use for requests about matching logic, explanations, consent, privacy, safety, API contracts, or UI behavior.

1. Read the smallest relevant source files and the two documents in `docs/` before editing.
2. Preserve the module boundaries under `services/backend/app/modules/`.
3. Update the generated contract when `/api/v1` changes: `pnpm --filter tongpin-web contracts`.
4. Add or update tests, create a Git commit, and run all checks before delivery.

### Verify

Use for requests to validate CI, a release, or the full product.

Run the commands in `references/operations.md`. A successful delivery requires the full validation set, not only the changed component.

## Product invariants

- Match only after the applicable `consent_scope` is active. Consent is deny-by-default and revocation must stop future recall.
- Keep raw source material separate from ranking. Browser recommendation DTOs must not contain `ranking_score`, `success_probability`, `confidence`, or raw explanation factors.
- Do not display a matching percentage, star rating, level, or fixed personality label. Explain using common signals, possible differences, unknowns, and ways to continue.
- Hard constraints and confirmed safety events veto ordinary recommendations.
- Never import unauthorized third-party chats, contacts, health, religion, sexual orientation, or political inference.
- Claims must retain evidence, confidence, recency, sensitivity, editability, and correction state internally.
- Outcome capture supports 7, 14, and 30 day windows; 30 day assessment includes growth alignment and boundary respect.
- Deletion must remove source, derived, cached, and relationship records while retaining only a content-free audit tombstone.

## Important paths

- Product overview and run instructions: `README.md`
- Product/data contract: `docs/matching-metrics-v0.1.md`
- Technical architecture: `docs/web-technical-architecture-v0.1.md`
- Startup and verification details: `references/operations.md`
- Backend entrypoint: `services/backend/app/main.py`
- Matching domain: `services/backend/app/modules/matching.py`
- User web app: `apps/web/app/`
- End-to-end/API tests: `tests/test_web_product_integration.py`
- UI policy tests: `apps/web/app/ui-policy.test.ts`

---

# Operations reference

## Local prerequisites

- Python 3.12
- Node.js 22+
- pnpm 11+
- Git

Use SQLite for local v0.1. PostgreSQL, Redis, Celery, and pgvector are available through Docker Compose for integration or staging-like runs.

## Fast start

Windows:

```powershell
cd <repository-root>
powershell -ExecutionPolicy Bypass -File .\scripts\start-local.ps1
```

macOS, Linux, or Git Bash:

```bash
cd <repository-root>
bash scripts/start-local.sh
```

Health endpoints:

```text
Web:     http://127.0.0.1:3000
API:     http://127.0.0.1:8000/api/v1/health
OpenAPI: http://127.0.0.1:8000/docs
```

The web app proxies `/api/v1` to FastAPI. Use port `3000` for users; port `8000` is the backend.

## Codespaces

Open:

```text
https://codespaces.new/selene4441-cmd/Soul-Mate
```

The dev container installs Python and Node dependencies, initializes SQLite, and starts both services. Open forwarded port `3000` from the Ports panel. Logs are written to:

```text
.devcontainer/logs/backend.log
.devcontainer/logs/web.log
```

Each Codespace has isolated data. Multiple users do not share a database unless the repository is deployed to a persistent host.

## Full product flow

1. Register or log in.
2. Grant `matching:v1`; grant `conversation:v1` and `outcomes:v1` only for the flows that will be exercised.
3. Complete the versioned questionnaire.
4. Review Claims and use “更像”, “不太像”, or “不确定” to correct them.
5. Generate relationship leads. Verify each lead contains common signals, differences, unknowns, and ways to continue.
6. Open a lead, confirm the explanation is traceable to Claims, then send an invitation.
7. Exchange messages after the relationship is connected.
8. Submit 7, 14, or 30 day outcome feedback.
9. Test revocation and deletion from the privacy page when privacy behavior is in scope.

## API smoke checks

Prefer `TestClient` for automated API flows because browser authentication uses HttpOnly cookies plus a CSRF token. Run the focused integration test:

```powershell
python -m pytest tests/test_web_product_integration.py -q
```

For a live process, use the web UI for state-changing flows. If using direct HTTP, first register/login, retain both cookies, and send the CSRF cookie value in the `X-CSRF-Token` header on every mutating request.

Representative endpoints:

```text
POST   /api/v1/auth/register
GET    /api/v1/auth/me
GET    /api/v1/consents
POST   /api/v1/consents
GET    /api/v1/questionnaire
POST   /api/v1/questionnaire/submissions
GET    /api/v1/claims
POST   /api/v1/recommendations
GET    /api/v1/recommendations/{candidate_id}
POST   /api/v1/invitations
GET    /api/v1/matches/{match_id}/messages
POST   /api/v1/matches/{match_id}/messages
POST   /api/v1/outcomes
DELETE /api/v1/privacy/me
```

## Validation

Run from the repository root:

```powershell
python -m ruff check services/backend tests
python -m pytest -q
pnpm install --frozen-lockfile
pnpm --filter tongpin-web contracts
git diff --exit-code -- packages/contracts/client.ts
pnpm --filter tongpin-web typecheck
pnpm --filter tongpin-web test
pnpm --filter tongpin-web build
```

Do not treat a successful Next.js build as a full privacy or matching test. The Python integration suite covers consent, CSRF, scoring-field leakage, invitations, WebSocket messages, deletion, and safety veto behavior.

## Troubleshooting

- `PROFILE_INCOMPLETE`: finish the required relationship-goal and hard-constraint questions.
- `CONSENT_REQUIRED`: grant the exact scope reported by the API; do not bypass consent checks.
- `CSRF_INVALID`: obtain a fresh session and send its `tongpin_csrf` cookie in `X-CSRF-Token`.
- No candidates: verify both users have active matching consent, valid non-expired Claims, compatible hard constraints, and no pending or confirmed high-risk safety event.
- Port conflict: stop the existing process or change both API origin and web port consistently.
- Codespaces WebSocket issue: the development origin policy allows `*.app.github.dev`; production must set `APP_ORIGIN` explicitly.