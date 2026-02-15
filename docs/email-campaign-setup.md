# Weekly Email Campaign Setup Guide

This guide covers the remaining setup steps for the weekly email campaign system.

## Prerequisites

- AWS Account with SES access
- Access to your domain's DNS settings (for domain verification)
- AWS credentials already added to `.env` (completed)

---

## Step 1: Verify Sender Domain in AWS SES

### 1.1 Create Domain Identity

1. Go to [AWS SES Console](https://console.aws.amazon.com/ses/)
2. Select region: **US East (N. Virginia)** `us-east-1`
3. Click **Verified identities** in the left sidebar
4. Click **Create identity**
5. Select **Domain**
6. Enter: `perchspot.com`
7. Check **Use a custom MAIL FROM domain** (optional but recommended)
8. Click **Create identity**

### 1.2 Add DNS Records

AWS will provide DKIM CNAME records. Add these to your domain DNS:

| Type | Name | Value |
|------|------|-------|
| CNAME | `xxxxxxxx._domainkey.perchspot.com` | `xxxxxxxx.dkim.amazonses.com` |
| CNAME | `yyyyyyyy._domainkey.perchspot.com` | `yyyyyyyy.dkim.amazonses.com` |
| CNAME | `zzzzzzzz._domainkey.perchspot.com` | `zzzzzzzz.dkim.amazonses.com` |

**Where to add DNS records:**
- If using Cloudflare: [Cloudflare Dashboard](https://dash.cloudflare.com/) → DNS
- If using Namecheap: Domain List → Manage → Advanced DNS
- If using GoDaddy: My Products → DNS

### 1.3 Wait for Verification

- DNS propagation takes **24-72 hours**
- Check status in SES Console → Verified identities → `perchspot.com`
- Status will change from "Pending" to "Verified"

---

## Step 2: Request Production Access (Exit Sandbox)

By default, SES is in "sandbox mode" which only allows sending to verified emails.

### 2.1 Submit Request

1. Go to [SES Console](https://console.aws.amazon.com/ses/)
2. Click **Account dashboard** in left sidebar
3. Under "Your account is in the sandbox", click **Request production access**
4. Fill out the form:
   - **Mail type**: Transactional
   - **Website URL**: https://perchspot.com
   - **Use case description**:
     ```
     We send weekly property digest emails to registered users who have
     searched for properties on our real estate analysis platform. Users
     can manage preferences and unsubscribe at any time via one-click
     unsubscribe links (CAN-SPAM compliant). Expected volume: 1,000-10,000
     emails per week.
     ```
5. Submit and wait for approval (usually 24-48 hours)

---

## Step 3: Test Email Sending (While in Sandbox)

### 3.1 Verify a Test Email Address

1. SES Console → Verified identities → Create identity
2. Select **Email address**
3. Enter your personal email (e.g., `yourname@gmail.com`)
4. Click the verification link sent to your email

### 3.2 Send a Test Email

```bash
# SSH into EC2 or run locally
docker compose exec celery_worker celery -A app.tasks.celery_app call send_test_digest_email --args='["yourname@gmail.com"]'
```

### 3.3 Check Logs

```bash
docker compose logs celery_worker --tail 50
```

---

## Step 4: Deploy to Production (EC2)

### 4.1 Update Production Environment

SSH into EC2:
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip
cd /opt/perchspot
```

Add AWS credentials to production `.env`:
```bash
sudo nano .env
```

Add these lines:
```
AWS_ACCESS_KEY_ID=AKIA3JXUYV6KFMTSYDAF
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
SES_FROM_EMAIL=Perchspot <hello@perchspot.com>
```

### 4.2 Pull and Deploy

```bash
# Pull latest code
git pull origin main

# Rebuild all services
sudo docker compose -f docker-compose.prod.yml up -d --build

# IMPORTANT: Restart nginx (caches backend IP)
sudo docker compose -f docker-compose.prod.yml restart nginx
```

### 4.3 Verify Deployment

```bash
# Check all services are running
sudo docker compose -f docker-compose.prod.yml ps

# Check celery beat schedule
sudo docker compose -f docker-compose.prod.yml logs celery_beat --tail 20

# Check for errors
sudo docker compose -f docker-compose.prod.yml logs backend --tail 50
```

---

## Step 5: Manual Campaign Trigger (Optional)

To manually trigger the weekly digest (instead of waiting for Sunday 9 AM):

```bash
# On EC2
sudo docker compose -f docker-compose.prod.yml exec celery_worker \
  celery -A app.tasks.celery_app call send_weekly_digest_emails
```

---

## Monitoring & Troubleshooting

### Check Email Campaign Logs

```sql
-- Connect to MySQL
SELECT * FROM email_campaign_logs ORDER BY created_at DESC LIMIT 20;
```

### Check User Email Preferences

```sql
SELECT u.email, ep.weekly_digest, ep.market_updates, ep.promotional
FROM users u
LEFT JOIN email_preferences ep ON u.id = ep.user_id
LIMIT 20;
```

### SES Sending Statistics

1. SES Console → Account dashboard
2. View sending statistics, bounces, complaints

### Common Issues

| Issue | Solution |
|-------|----------|
| "Email address not verified" | You're in sandbox mode. Verify recipient or request production access |
| "Access Denied" | Check AWS credentials in `.env` and IAM permissions |
| "MessageRejected" | Domain not verified yet. Wait for DNS propagation |
| Emails going to spam | Complete domain verification with DKIM |

---

## Email Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `send_weekly_digest_emails` | Sunday 9:00 AM UTC | Weekly property digest to all opted-in users |

To modify the schedule, edit `backend/app/tasks/celery_app.py`:

```python
'send-weekly-digest-sunday': {
    'task': 'send_weekly_digest_emails',
    'schedule': crontab(day_of_week='sunday', hour='9', minute='0'),
    'options': {'expires': 7200},
}
```

---

## Cost Estimate

| Volume | SES Cost | Notes |
|--------|----------|-------|
| 1,000 emails/week | ~$0.10/week | First 62,000/month free if sent from EC2 |
| 10,000 emails/week | ~$1.00/week | |
| 100,000 emails/week | ~$10.00/week | |

SES pricing: $0.10 per 1,000 emails

---

## Checklist

- [ ] Domain identity created in SES
- [ ] CNAME records added to DNS
- [ ] Domain verified (24-72 hours)
- [ ] Production access requested
- [ ] Production access approved
- [ ] Test email sent successfully
- [ ] Deployed to EC2
- [ ] Verified celery beat is running
