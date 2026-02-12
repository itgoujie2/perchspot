# Perchspot System Flow Documentation

## Overview

Perchspot is a real estate analysis platform that takes a Redfin property URL and generates comprehensive analysis using AI. The system uses Server-Sent Events (SSE) for real-time streaming of analysis results.

---

## High-Level Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   Backend   │────▶│  Playwright │────▶│   Redfin    │
│   (React)   │     │   (FastAPI) │     │  (Browser)  │     │   Website   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Claude AI  │
                    │   (Vision)  │
                    └─────────────┘
```

---

## Step-by-Step Flow

### Step 1: User Submits Redfin URL

**Frontend**: `frontend/src/pages/ChatPage.tsx`

1. User pastes a Redfin property URL into the input field
2. Frontend validates URL format (must contain `redfin.com`)
3. Opens SSE connection to backend: `GET /api/v1/analysis/stream?url={redfin_url}`

**Cost**: $0.00

---

### Step 2: Backend Receives Request

**Backend Entry Point**: `backend/app/api/v1/endpoints/streaming_analysis.py`

```python
@router.get("/stream")
async def stream_analysis(url: str, ...):
    # Validate URL, check credits, start streaming
```

1. Validates Redfin URL format
2. Checks user authentication (optional - anonymous users get 1 free analysis)
3. If authenticated, verifies credit balance
4. Initializes `StreamingOrchestrator` to manage analysis

**Cost**: $0.00

---

### Step 3: Screenshot Capture

**File**: `backend/app/services/agent/streaming_orchestrator.py`
**Uses**: `backend/app/services/scraper/screenshot.py`

1. Launches headless Chromium browser via Playwright
2. Navigates to Redfin property page
3. Takes **10 sequential screenshots** scrolling down the page:
   - Each screenshot is 1280x800 pixels
   - Scrolls 700px between shots to capture full listing
   - Handles cookie banners and popups
4. Screenshots saved to `backend/screenshots/{address}/page_{i}.png`

**Cost**: $0.00 (local browser automation)

---

### Step 4: Vision Extraction

**File**: `backend/app/services/agent/streaming_orchestrator.py`

1. All 10 screenshots sent to Claude Vision in a single API call
2. Claude extracts structured property data:
   - Price, beds, baths, sqft, lot size
   - Year built, HOA, property type
   - Address, MLS number
   - Description, features, schools
   - Listing agent info

**Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
**Token Usage** (typical):
- Input: ~25,000 tokens (10 images + prompt)
- Output: ~1,500 tokens

**Cost Calculation**:
```
Input:  25,000 tokens × $3.00/1M = $0.075
Output:  1,500 tokens × $15.00/1M = $0.0225
Total: ~$0.08 per extraction
```

**Cost**: ~$0.08

---

### Step 5: Analysis Skills Execution

**File**: `backend/app/services/agent/streaming_orchestrator.py`

Four specialized analysis skills run in sequence, each streaming results to the user:

#### 5a. Property Skill

**File**: `backend/app/services/agent/skills/property.py`

Analyzes:
- Construction quality and materials
- Age-related concerns (roof, HVAC, foundation)
- Maintenance considerations
- Potential issues

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Token Usage**:
- Input: ~4,000 tokens
- Output: ~800 tokens

**Cost**: ~$0.008

#### 5b. Location Skill

**File**: `backend/app/services/agent/skills/location.py`

Analyzes:
- Neighborhood characteristics
- Commute patterns
- Walkability and transit
- Local amenities
- Market context

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Token Usage**:
- Input: ~4,000 tokens
- Output: ~800 tokens

**Cost**: ~$0.008

#### 5c. School Skill

**File**: `backend/app/services/agent/skills/school.py`

Analyzes:
- School district quality
- Individual school ratings
- Educational options nearby
- Impact on property value

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Token Usage**:
- Input: ~4,000 tokens
- Output: ~800 tokens

**Cost**: ~$0.008

#### 5d. Investment Skill

**File**: `backend/app/services/agent/skills/investment.py`

Analyzes:
- Price per square foot comparison
- Rental potential
- Appreciation outlook
- ROI considerations
- Market timing

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Token Usage**:
- Input: ~5,000 tokens
- Output: ~1,000 tokens

**Cost**: ~$0.01

---

### Step 6: Notes Storage

**File**: `backend/app/services/agent/tools/notes_manager.py`

1. All analysis results saved to `backend/notes/{sanitized_address}.md`
2. Stored for future chat context
3. Enables follow-up questions about the property

**Cost**: $0.00 (local file storage)

---

### Step 7: SSE Response Streaming

**File**: `backend/app/api/v1/endpoints/streaming_analysis.py`

Results streamed to frontend in real-time:
```
event: extraction
data: {"type": "extraction", "content": {...}}

event: property
data: {"type": "property", "content": "..."}

event: location
data: {"type": "location", "content": "..."}

event: school
data: {"type": "school", "content": "..."}

event: investment
data: {"type": "investment", "content": "..."}

event: complete
data: {"type": "complete", "cost": 0.127}
```

**Cost**: $0.00

---

## Total Cost Per Analysis

| Step | Model | Input Tokens | Output Tokens | Cost |
|------|-------|--------------|---------------|------|
| Vision Extraction | Claude Sonnet 4 | ~25,000 | ~1,500 | $0.080 |
| Property Skill | Claude Haiku 4.5 | ~4,000 | ~800 | $0.008 |
| Location Skill | Claude Haiku 4.5 | ~4,000 | ~800 | $0.008 |
| School Skill | Claude Haiku 4.5 | ~4,000 | ~800 | $0.008 |
| Investment Skill | Claude Haiku 4.5 | ~5,000 | ~1,000 | $0.010 |
| **Total Raw Cost** | | | | **~$0.114** |

### Pricing Margin

The system applies a 50% pricing margin for user-facing costs:

```
User Cost = Raw Cost / (1 - 0.50) = Raw Cost × 2
```

| Cost Type | Amount |
|-----------|--------|
| Raw API Cost | ~$0.114 |
| **User Pays** | **~$0.23** |

---

## Chat System Flow

### User Asks Follow-up Question

**File**: `backend/app/api/v1/endpoints/chat.py`

1. User sends message via `POST /api/v1/chat`
2. System loads:
   - Previous conversation history (in-memory)
   - Property notes from analysis (if address provided)
   - Relevant knowledge files (keyword matching)
   - User memories (if authenticated)

3. Knowledge loader checks for relevant topics:
   - Foundation, roof, siding, HVAC, schools
   - Market-specific info (Seattle, Bay Area, NYC, Austin, LA)

4. Claude generates response with tools:
   - Web search (for current rates, market data)
   - Save memory (remembers user preferences)
   - Property recommendations (similar homes)

**Model**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
**Typical Cost**: ~$0.005-0.02 per message

---

## Model Summary

| Usage | Model | Input Cost | Output Cost |
|-------|-------|------------|-------------|
| Vision Extraction | Claude Sonnet 4 | $3.00/1M | $15.00/1M |
| All Analysis Skills | Claude Haiku 4.5 | $1.00/1M | $5.00/1M |
| Chat | Claude Haiku 4.5 | $1.00/1M | $5.00/1M |
| Web Search | Anthropic API | $0.01/search | - |

---

## Key Files Reference

### API Endpoints
- `backend/app/api/v1/endpoints/streaming_analysis.py` - Main analysis endpoint
- `backend/app/api/v1/endpoints/chat.py` - Chat endpoint
- `backend/app/api/v1/endpoints/auth.py` - Authentication
- `backend/app/api/v1/endpoints/payment.py` - Stripe payments

### Core Services
- `backend/app/services/agent/streaming_orchestrator.py` - Analysis orchestration
- `backend/app/services/scraper/screenshot.py` - Screenshot capture
- `backend/app/services/knowledge/knowledge_loader.py` - Knowledge file loading

### Analysis Skills
- `backend/app/services/agent/skills/property.py`
- `backend/app/services/agent/skills/location.py`
- `backend/app/services/agent/skills/school.py`
- `backend/app/services/agent/skills/investment.py`

### Knowledge Base
- `backend/knowledge/property/` - Property-related knowledge
- `backend/knowledge/location/` - Market-specific knowledge

### Frontend
- `frontend/src/pages/ChatPage.tsx` - Main chat interface
- `frontend/src/services/api.ts` - API client

---

## Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
DATABASE_URL=postgresql://...

# Optional
PRICING_MARGIN=0.50  # 50% margin on API costs
FREE_CREDITS=0.50    # Credits for new users
```

---

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| frontend | 3000 | React app |
| backend | 8000 | FastAPI server |
| postgres | 5432 | Database |
| nginx | 80/443 | Reverse proxy (production) |

---

## Cost Optimization Notes

1. **Screenshot approach** avoids Redfin API costs and rate limits
2. **Haiku for skills** is 3x cheaper than Sonnet, sufficient for text analysis
3. **Single vision call** for all 10 screenshots batches efficiently
4. **Knowledge files** loaded on-demand, not embedded in every request
5. **50% margin** covers infrastructure, provides profit buffer
