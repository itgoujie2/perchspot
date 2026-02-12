# Analysis: Property Image Download & Vision Analysis

## Current State

The system takes **10 page screenshots** of Redfin listing and sends them to Claude Vision in a single API call to extract structured data (price, beds, baths, etc.). **No individual property photos are downloaded or analyzed.**

Current cost per property: **~$0.05-0.08** (one Claude Sonnet vision call with 10 screenshots)

---

## Proposed Feature

Download individual property photos from Redfin and analyze each with vision API to extract:
- Kitchen quality (high-end appliances, countertops, fixtures)
- Bathroom finishes (tile quality, fixtures, vanities)
- Flooring type and condition
- Overall finish level (builder-grade vs luxury)
- Renovation age/quality
- Staging vs lived-in condition

---

## Cost Analysis

### Vision API Pricing (Claude Sonnet 4)
- Input: $3/1M tokens (~$0.003 per 1000 tokens)
- Output: $15/1M tokens (~$0.015 per 1000 tokens)
- **Image tokens**: ~1,600 tokens per 1024x1024 image

### Cost Per Image Analysis
| Component | Tokens | Cost |
|-----------|--------|------|
| Image (1024px) | ~1,600 | $0.0048 |
| Prompt | ~500 | $0.0015 |
| Response | ~300 | $0.0045 |
| **Per Image Total** | | **~$0.01** |

### Cost Per Property (Typical Redfin Listing: 20-40 photos)
| Scenario | Images | Raw Cost | With 5x Margin |
|----------|--------|----------|----------------|
| Minimal | 10 | $0.10 | $0.50 |
| Typical | 25 | $0.25 | $1.25 |
| Large listing | 40 | $0.40 | $2.00 |

### Current vs New Total Cost
| Item | Current | With Image Analysis |
|------|---------|---------------------|
| Screenshot extraction | $0.06 | $0.06 |
| Analysis skills | $0.02 | $0.02 |
| Image analysis (25 photos) | $0.00 | $0.25 |
| **Total (raw)** | **$0.08** | **$0.33** |
| **User pays (5x margin)** | **$0.40** | **$1.65** |

**Cost increase: ~4x per analysis**

---

## Pros

1. **Richer Property Insights**
   - Detect high-end finishes (Viking, Sub-Zero, Wolf appliances)
   - Identify renovation quality and age
   - Assess overall condition beyond listing description

2. **Better Investment Analysis**
   - Estimate actual property condition vs listing hype
   - Identify value-add opportunities (outdated kitchens, etc.)
   - Compare finish level to price point

3. **Competitive Differentiation**
   - No competitor does per-image quality analysis
   - Unique selling point for premium users

4. **Objective Assessment**
   - Removes bias from listing descriptions
   - Consistent evaluation criteria across properties

---

## Cons

1. **Significant Cost Increase**
   - 4x increase in cost per analysis
   - May price out casual users
   - Margin pressure if competitors undercut

2. **Redfin Image Access**
   - Need to scrape image URLs (terms of service risk)
   - Image URLs may be protected or rate-limited
   - CDN/hotlinking blocks possible

3. **Processing Time**
   - 25 images × API calls = slower analysis
   - Could batch, but still adds latency
   - User experience impact

4. **Storage Costs**
   - Images need temporary storage for processing
   - S3 costs if retaining images
   - Cleanup/retention policies needed

5. **Diminishing Returns**
   - Many photos are similar angles
   - Exterior shots less useful for finish analysis
   - Agent photos may be staged/filtered

6. **Accuracy Concerns**
   - Wide-angle lens distortion
   - Professional photography hides flaws
   - Hard to distinguish granite from quartz in photos

---

## Implementation Complexity

| Component | Effort | Risk |
|-----------|--------|------|
| Scrape image URLs from Redfin | Medium | High (TOS, anti-bot) |
| Download images | Low | Low |
| Store to S3 temporarily | Low | Low |
| Vision API calls (batch) | Medium | Low |
| Parse/structure insights | Medium | Medium |
| Integrate into analysis | Medium | Low |
| **Total** | **~3-5 days** | **Medium** |

---

## Alternatives

### Option A: Analyze Existing Screenshots Only
- Already have 10 screenshots including interior photos
- Add prompts to extract finish quality from visible photos
- **Cost: $0** (already paying for screenshots)
- **Accuracy: Lower** (limited angles, small images)

### Option B: Smart Image Selection
- Download all images, but only analyze 5-8 key ones
- Select: kitchen, bathrooms, living areas
- Skip: exterior, similar angles, yard
- **Cost: ~$0.08 extra** (~$0.16 total raw)

### Option C: Premium Tier Only
- Offer image analysis as premium feature
- Free/basic: screenshot extraction only
- Premium: full image analysis
- **User pays: $2-3 for premium analysis**

---

## Recommendation

**Start with Option A** - enhance existing screenshot analysis with finish quality prompts. Zero additional cost, quick to implement.

If users demand more detail, implement **Option B** (smart selection) as a premium feature.

Full image analysis (Option C) only makes sense if:
- Users willing to pay $2+ per analysis
- Clear competitive advantage demonstrated
- Redfin image access is stable

---

## Verification (if implementing)

1. Test image URL extraction from Redfin
2. Verify download reliability (rate limits, blocks)
3. Benchmark vision API accuracy on finish detection
4. A/B test user value perception
5. Monitor cost/revenue impact
