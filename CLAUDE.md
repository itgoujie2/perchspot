# Claude Memory - Perchspot

## Project Info
- **Business Name**: Perchspot
- **Domains**: perchspot.com, perchspot.ai (to register)
- **Logo**: `frontend/src/assets/logo.svg`

## Development Notes

### After Making Changes
**Always restart services after code changes without waiting for user to ask:**

| Change Type | Command |
|-------------|---------|
| Backend code (.py files) | `docker compose restart backend` |
| Frontend code (.tsx/.css) | `docker compose restart frontend` |
| `.env` file changes | `docker compose up -d backend` (must recreate, not restart) |
| requirements.txt | `docker compose up -d --build backend` |
| package.json | `docker compose up -d --build frontend` |

### Stripe Testing
- Test mode keys start with `sk_test_` and `pk_test_`
- Live mode keys start with `sk_live_` and `pk_live_`
- Test card: `4242 4242 4242 4242` (any future expiry, any CVC)
- Run `stripe listen --forward-to localhost:8000/api/v1/payments/webhook` for local webhook testing
- The webhook secret from `stripe listen` must be set in `.env` as `STRIPE_WEBHOOK_SECRET`
