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