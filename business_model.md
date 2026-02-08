# Simple Credit Model: Margin Comparison (with Caching)

## Your Costs

| Action | Your Cost |
|---|---|
| Property Analysis (first time) | $0.31 |
| Property Analysis (cached) | $0.00 |
| Chat Message | $0.005 |
| Infrastructure (fixed) | ~$150/mo |

With full analysis caching, repeat analyses of the same property cost nothing.
Cache hit rate depends on user overlap — users in the same metro analyzing popular listings = higher cache rate.

---

## What Users Pay at Each Margin

| Margin | Analysis Price | Chat Price |
|---|---|---|
| 50% | $0.62 | $0.01 |
| 67% | $0.93 | $0.015 |
| 75% | $1.24 | $0.02 |
| 80% | $1.55 | $0.025 |
| 85% | $2.07 | $0.033 |
| 90% | $3.10 | $0.05 |

---

## Monthly Profit: Margin x Cache Rate

Assumes: 5 analyses/user/month, 20 chat messages/user/month, $150/mo infrastructure.
Revenue stays the same regardless of cache rate — users pay per analysis either way.

### 100 Users

| Margin | User Pays/mo | Revenue | No Cache | 30% Cache | 50% Cache |
|---|---|---|---|---|---|
| 50% | $3.30 | $330 | $15 | $62 | $93 |
| 67% | $4.95 | $495 | $180 | $227 | $258 |
| 75% | $6.60 | $660 | $345 | $392 | $423 |
| 80% | $8.25 | $825 | $510 | $557 | $588 |
| 85% | $11.01 | $1,101 | $786 | $833 | $864 |
| 90% | $16.50 | $1,650 | $1,335 | $1,382 | $1,413 |

Your costs: No cache $315 | 30% cache $269 | 50% cache $238

### 500 Users

| Margin | User Pays/mo | Revenue | No Cache | 30% Cache | 50% Cache |
|---|---|---|---|---|---|
| 50% | $3.30 | $1,650 | $675 | $908 | $1,063 |
| 67% | $4.95 | $2,475 | $1,500 | $1,733 | $1,888 |
| 75% | $6.60 | $3,300 | $2,325 | $2,558 | $2,713 |
| 80% | $8.25 | $4,125 | $3,150 | $3,383 | $3,538 |
| 85% | $11.01 | $5,505 | $4,530 | $4,763 | $4,918 |
| 90% | $16.50 | $8,250 | $7,275 | $7,508 | $7,663 |

Your costs: No cache $975 | 30% cache $743 | 50% cache $588

### 1,000 Users

| Margin | User Pays/mo | Revenue | No Cache | 30% Cache | 50% Cache |
|---|---|---|---|---|---|
| 50% | $3.30 | $3,300 | $1,500 | $1,965 | $2,275 |
| 67% | $4.95 | $4,950 | $3,150 | $3,615 | $3,925 |
| 75% | $6.60 | $6,600 | $4,800 | $5,265 | $5,575 |
| 80% | $8.25 | $8,250 | $6,450 | $6,915 | $7,225 |
| 85% | $11.01 | $11,010 | $9,210 | $9,675 | $9,985 |
| 90% | $16.50 | $16,500 | $14,700 | $15,165 | $15,475 |

Your costs: No cache $1,800 | 30% cache $1,335 | 50% cache $1,025

---

## Summary

Caching improves profit but the margin you set matters far more than the cache hit rate. The difference between 75% and 85% margin at 500 users ($2,325 vs $4,530) dwarfs the difference between 0% and 50% cache at any single margin (~$388).

Bottom line: Pick your margin based on what price feels right for users. Caching is a nice bonus that silently boosts your effective margin by a few percentage points — but it's not the main lever.

| Margin | Analysis Price | Verdict |
|---|---|---|
| 50% | $0.62 | Too thin — barely covers infra at small scale |
| 67% | $0.93 | Workable but lean |
| 75% | $1.24 | Good balance — cheap for users, solid profit |
| 80% | $1.55 | Sweet spot — still affordable, strong margins |
| 85% | $2.07 | Strong profit, starting to feel pricey |
| 90% | $3.10 | Risk of low adoption |

---

## Stripe Credit Purchases

Users buy credits at a flat rate: 1 credit = $1. No volume discounts.
Preset buttons for $5, $10, $20 plus a custom amount input ($1–$100).

This keeps the margin math simple — the effective margin is the same regardless of purchase size, minus Stripe fees.

### Stripe Fees (2.9% + $0.30 per transaction)

| Purchase | Stripe Fee | Net Revenue | Effective $/Cr | Effective Margin |
|---|---|---|---|---|
| $5 | $0.45 | $4.55 | $0.91 | 66% |
| $10 | $0.59 | $9.41 | $0.94 | 67% |
| $20 | $0.88 | $19.12 | $0.96 | 68% |
| $50 | $1.75 | $48.25 | $0.97 | 68% |

Stripe's fixed $0.30 hurts small purchases most (9% total fee on $5, vs 4.4% on $20).
Larger purchases converge toward ~69% effective margin.
