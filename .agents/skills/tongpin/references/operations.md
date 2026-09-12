# Tongpin operations reference

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