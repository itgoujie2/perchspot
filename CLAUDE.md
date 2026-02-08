# Claude Memory - Perchspot

## Project Info
- **Business Name**: Perchspot
- **Domains**: perchspot.com, perchspot.ai (to register)
- **Logo**: `frontend/src/assets/logo.svg`

## Development Notes

### After Making Changes
**Always do BOTH steps after code changes without waiting for user to ask:**

#### Step 1: Commit and Push to GitHub
```bash
git add -A
git commit -m "Description of changes

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
git push origin main
```

#### Step 2: Restart Local Docker Services

| Change Type | Command |
|-------------|---------|
| Backend code (.py files) | `docker compose restart backend` |
| Frontend code (.tsx/.css) | `docker compose restart frontend` |
| `.env` file changes | `docker compose up -d backend` (must recreate, not restart) |
| requirements.txt | `docker compose up -d --build backend` |
| package.json | `docker compose up -d --build frontend` |

### Production Deployment (EC2)
After pushing changes, remind user to update production:
```bash
# On EC2:
cd /opt/perchspot
git pull origin main
sudo docker compose -f docker-compose.prod.yml up -d --build
```

**IMPORTANT: Always restart nginx after rebuilding backend!**
```bash
sudo docker compose -f docker-compose.prod.yml restart nginx
```
Nginx caches the backend container IP. When backend restarts with a new IP, nginx can't find it (502 error / login fails). Always restart nginx after any backend rebuild.

### Stripe Testing
- Test mode keys start with `sk_test_` and `pk_test_`
- Live mode keys start with `sk_live_` and `pk_live_`
- Test card: `4242 4242 4242 4242` (any future expiry, any CVC)
- Run `stripe listen --forward-to localhost:8000/api/v1/payments/webhook` for local webhook testing
- The webhook secret from `stripe listen` must be set in `.env` as `STRIPE_WEBHOOK_SECRET`
