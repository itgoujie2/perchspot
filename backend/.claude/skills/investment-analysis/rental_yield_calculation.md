# Rental Yield & Investment Metric Formulas

All metrics are pre-computed in `InvestmentSkill._compute_metrics()` before sending to Claude. This document records the formulas and assumptions.

## Gross Rental Yield
```
gross_yield = (monthly_rent * 12) / purchase_price * 100
```
Simple ratio of annual rent to price. Does not account for expenses.

## Net Operating Income (NOI)
```
annual_rent = monthly_rent * 12
vacancy_loss = annual_rent * 0.05           # 5% vacancy rate
effective_income = annual_rent - vacancy_loss

operating_expenses =
    property_tax                             # from listing data
  + insurance    (= purchase_price * 0.0035) # ~0.35% of value/year
  + maintenance  (= purchase_price * 0.01)   # ~1% of value/year (rule of thumb)
  + hoa_annual                               # HOA fee * 12 (or adjusted for frequency)

NOI = effective_income - operating_expenses
```

### Assumptions
- **5% vacancy rate**: Standard assumption for single-family residential. Actual rates vary by market (2-3% in tight markets, 8-10% in soft markets).
- **0.35% insurance**: National average for homeowner's insurance as percentage of home value.
- **1% maintenance**: Common rule of thumb. Older homes may need 1.5-2%. New construction may be 0.5%.
- **Property tax**: Uses actual data from listing when available. Falls back to 1% of purchase price if missing.

## Cap Rate
```
cap_rate = NOI / purchase_price * 100
```
Measures return assuming all-cash purchase. Most useful for comparing properties.

## Gross Rent Multiplier (GRM)
```
GRM = purchase_price / (monthly_rent * 12)
```
Quick ratio — lower is better for investors. Same calculation as price-to-rent ratio.

## Cash-on-Cash Return
```
down_payment = purchase_price * 0.20
loan = purchase_price * 0.80
r = 0.07 / 12                               # monthly rate (7% annual)
n = 360                                      # 30-year term

monthly_mortgage = loan * (r * (1+r)^n) / ((1+r)^n - 1)
annual_debt_service = monthly_mortgage * 12
annual_cash_flow = NOI - annual_debt_service
cash_on_cash = annual_cash_flow / down_payment * 100
```

### Financing Assumptions
- **20% down payment**: Conventional investment property minimum
- **7% interest rate**: Approximate current market rate for investment properties (typically 0.5-0.75% above primary residence rates)
- **30-year fixed**: Standard amortization

## Price vs Estimate Spread
```
spread_pct = (redfin_estimate - list_price) / list_price * 100
```
Positive spread = listed below estimated value (potential deal).

## Monthly Cash Flow
```
monthly_cash_flow = (NOI - annual_debt_service) / 12
```
What the investor actually takes home (or pays out) per month after all expenses and mortgage.
