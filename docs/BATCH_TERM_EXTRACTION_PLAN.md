# Batch Term Extraction Plan

**Status:** Not implemented - saved for future consideration
**Created:** 2026-02-11
**Reason to defer:** Gain not obvious, current LLM-based extraction works well

---

## Problem

PropertySkill currently uses Claude Haiku to extract search terms from each property description in real-time. This:
- Adds ~10-20s latency per analysis
- Uses API calls that could be avoided
- Relies on LLM to discover terms each time (not always consistent)

## Proposed Solution

Pre-extract terms from accumulated property descriptions using batch LLM processing:

1. **Accumulate** - Collect descriptions from all analyzed properties
2. **Batch process** - Periodically run LLM extraction (Celery task)
3. **Store** - Save extracted terms in lookup file/database
4. **Fast match** - Use string matching during analysis instead of LLM

```
┌─────────────────────────────────────────────────────────┐
│  Property descriptions accumulate over time             │
└─────────────────────┬───────────────────────────────────┘
                      ↓ (Celery task, weekly or manual)
┌─────────────────────────────────────────────────────────┐
│  LLM extracts terms by category:                        │
│  - builders, neighborhoods, architecture_styles,        │
│  - kitchen_brands, notable_features                     │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  MySQL table or JSON file (extracted_terms)             │
└─────────────────────┬───────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│  PropertySkill: fast string matching against terms      │
│  Falls back to LLM for new/unknown terms                │
└─────────────────────────────────────────────────────────┘
```

## Term Categories

| Category | Examples |
|----------|----------|
| `builders` | Toll Brothers, Murray Franklyn, Polygon, Lennar |
| `neighborhoods` | Bridle Trails, Somerset, Lake Hills, Crossroads |
| `architecture_styles` | Craftsman, Mid-century Modern, Contemporary, Tudor |
| `kitchen_brands` | Sub-Zero, Wolf, Viking, Thermador, Miele, Bosch |
| `notable_features` | ADU, mother-in-law suite, solar panels, EV charger, wine cellar |

## Storage Options

### Option 1: MySQL Table (Recommended for production)
```sql
CREATE TABLE extracted_terms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    term VARCHAR(100) NOT NULL,
    frequency INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_term (category, term)
);
```

### Option 2: JSON File in Repo (Simpler)
```json
// backend/app/config/extracted_terms.json
{
  "builders": ["toll brothers", "murray franklyn", "polygon"],
  "neighborhoods": ["bridle trails", "somerset"],
  "architecture_styles": ["craftsman", "mid-century modern"],
  "kitchen_brands": ["sub-zero", "wolf", "viking"],
  "notable_features": ["adu", "solar panels", "ev charger"]
}
```

## Implementation Files

### 1. Term Extractor Service
`backend/app/services/knowledge/term_extractor.py`

```python
"""
Term Extractor Service - Batch extraction of terms from property descriptions.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Set
import logging
from anthropic import Anthropic

logger = logging.getLogger(__name__)

TERMS_FILE = Path(__file__).parent.parent.parent / "config" / "extracted_terms.json"
PROPERTY_DATA_DIR = Path("/app/property_data")

CATEGORIES = [
    "builders",
    "neighborhoods",
    "architecture_styles",
    "kitchen_brands",
    "notable_features",
]


class TermExtractor:
    def __init__(self):
        self._terms: Dict[str, Set[str]] = {cat: set() for cat in CATEGORIES}
        self._load_terms()

    def _load_terms(self):
        """Load existing terms from JSON file."""
        if TERMS_FILE.exists():
            with open(TERMS_FILE) as f:
                data = json.load(f)
                for cat in CATEGORIES:
                    self._terms[cat] = set(data.get(cat, []))

    def save_terms(self):
        """Save terms to JSON file."""
        TERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TERMS_FILE, 'w') as f:
            json.dump({cat: sorted(terms) for cat, terms in self._terms.items()}, f, indent=2)

    def get_terms(self, category: str) -> List[str]:
        return list(self._terms.get(category, []))

    def match_terms_in_description(self, description: str) -> Dict[str, List[str]]:
        """Find all matching terms in a property description."""
        description_lower = description.lower()
        matches = {}
        for category, terms in self._terms.items():
            category_matches = [t for t in terms if t.lower() in description_lower]
            if category_matches:
                matches[category] = category_matches
        return matches

    def extract_from_all_properties(self) -> Dict[str, List[str]]:
        """Extract terms from all property descriptions using LLM."""
        descriptions = self._collect_descriptions()
        if not descriptions:
            return self.get_all_terms()

        blob = "\n\n---\n\n".join(descriptions)[:50000]  # Limit context
        new_terms = self._extract_with_llm(blob)

        # Merge with existing (additive)
        for cat, terms in new_terms.items():
            self._terms[cat].update(t.lower() for t in terms)

        self.save_terms()
        return self.get_all_terms()

    def _collect_descriptions(self) -> List[str]:
        """Collect descriptions from property JSON files."""
        descriptions = []
        for json_file in PROPERTY_DATA_DIR.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    desc = data.get("property", {}).get("description", "")
                    if desc and len(desc) > 50:
                        descriptions.append(desc)
            except Exception:
                pass
        return descriptions

    def _extract_with_llm(self, blob: str) -> Dict[str, List[str]]:
        """Use Claude to extract terms from description blob."""
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        prompt = f"""Extract specific named entities from these property descriptions.

PROPERTY DESCRIPTIONS:
{blob}

---

Extract terms into these categories (ONLY specific proper nouns/brand names):

1. **builders** - Builder/developer company names
2. **neighborhoods** - Specific neighborhood/community names
3. **architecture_styles** - Named architectural styles
4. **kitchen_brands** - Premium appliance/fixture brands
5. **notable_features** - Unusual features (ADU, solar, EV charger, etc.)

DO NOT include generic terms like "modern", "updated", "granite counters".

Return JSON object with category names as keys and arrays of terms as values.
Return ONLY valid JSON."""

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1].replace("json", "", 1).strip()

        return json.loads(text)


# Singleton
_extractor = None
def get_term_extractor():
    global _extractor
    if _extractor is None:
        _extractor = TermExtractor()
    return _extractor
```

### 2. Celery Task
`backend/app/tasks/term_extraction_tasks.py`

```python
from app.tasks.celery_app import celery_app
from app.services.knowledge.term_extractor import get_term_extractor
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name="extract_property_terms")
def extract_property_terms():
    """Extract terms from all property descriptions."""
    logger.info("Starting term extraction task")
    extractor = get_term_extractor()
    terms = extractor.extract_from_all_properties()
    logger.info(f"Extraction complete: {sum(len(v) for v in terms.values())} terms")
    return terms
```

### 3. Schedule (optional)
Add to `celery_app.py`:

```python
'extract-terms-weekly': {
    'task': 'extract_property_terms',
    'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3am
}
```

### 4. PropertySkill Integration
Modify `_extract_property_queries` to try fast matching first:

```python
async def _extract_property_queries(self, prop, details, features, region_info):
    from app.services.knowledge.term_extractor import get_term_extractor

    description = (prop.get('description') or '').lower()
    extractor = get_term_extractor()

    # Try fast matching against pre-extracted terms
    matches = extractor.match_terms_in_description(description)
    fast_queries = []
    for category, terms in matches.items():
        fast_queries.extend(terms[:1])  # One per category

    # If we got enough matches, skip LLM call
    if len(fast_queries) >= 3:
        # Add standard queries
        if city:
            fast_queries.append(f"{city} neighborhood")
        if prop_type and region:
            fast_queries.append(f"{prop_type} in {region}")
        return fast_queries[:7]

    # Fall back to LLM extraction (existing code)
    return await self._extract_with_llm(prop, details, features, region_info)
```

### 5. Config Flag for A/B Testing
Add to `backend/app/config.py`:

```python
# Term extraction mode: "llm" (current), "fast" (pre-extracted only), "hybrid" (fast + llm fallback)
TERM_EXTRACTION_MODE: str = os.getenv("TERM_EXTRACTION_MODE", "llm")
```

## API Endpoints (Optional)

```python
# backend/app/api/v1/knowledge.py

@router.post("/terms/extract")
async def trigger_term_extraction():
    """Manually trigger term extraction."""
    from app.tasks.term_extraction_tasks import extract_property_terms
    task = extract_property_terms.delay()
    return {"task_id": task.id, "status": "started"}

@router.get("/terms")
async def get_extracted_terms():
    """Get all extracted terms."""
    from app.services.knowledge.term_extractor import get_term_extractor
    return get_term_extractor().get_all_terms()
```

## Verification Steps

1. **Create initial terms file:**
   ```bash
   mkdir -p backend/app/config
   echo '{"builders":[],"neighborhoods":[],"architecture_styles":[],"kitchen_brands":[],"notable_features":[]}' > backend/app/config/extracted_terms.json
   ```

2. **Run extraction manually:**
   ```bash
   docker compose exec backend python -c "
   from app.services.knowledge.term_extractor import get_term_extractor
   terms = get_term_extractor().extract_from_all_properties()
   print(terms)
   "
   ```

3. **Test matching:**
   ```bash
   docker compose exec backend python -c "
   from app.services.knowledge.term_extractor import get_term_extractor
   matches = get_term_extractor().match_terms_in_description('Beautiful Murray Franklyn craftsman in Bridle Trails with Sub-Zero fridge')
   print(matches)
   "
   ```

## Expected Benefits

- **Latency reduction:** Skip Haiku call when terms match (~10-20s savings)
- **Consistency:** Same terms extracted regardless of LLM variability
- **Cost reduction:** Fewer API calls per analysis
- **Discoverability:** Accumulated terms grow over time

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| New terms not recognized | Hybrid mode falls back to LLM |
| Stale terms | Weekly refresh via Celery |
| Storage issues in prod | Use MySQL instead of file |
| LLM extraction quality | Human review of extracted terms |

## Rollback

Set `TERM_EXTRACTION_MODE=llm` to disable and use current behavior.
