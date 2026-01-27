# Housing Analysis System

AI-powered property analysis system that provides comprehensive reports with scores across multiple categories.

## Features

- **Property Condition Analysis (30%)** - AI vision analysis of property images + text analysis
- **Location Quality (25%)** - Neighborhood, amenities, transit, and walkability analysis
- **Schools (20%)** - School ratings and proximity analysis
- **Investment Value (25%)** - Market analysis, price comparison, and ROI estimation

## Tech Stack

### Backend
- **FastAPI** - Async Python web framework
- **PostgreSQL** - Primary database
- **Redis** - Caching and rate limiting
- **Celery** - Async task queue
- **OpenAI GPT-4o** - LLM for analysis
- **SQLAlchemy** - ORM

### Frontend
- **React + TypeScript**
- **Material-UI** - Component library
- **React Query** - State management
- **Vite** - Build tool

### Infrastructure
- **Docker + Docker Compose** - Containerization
- **MinIO** - S3-compatible object storage (local development)
- **PostgreSQL 15** - Database
- **Redis 7** - Cache

## Prerequisites

- Docker and Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.11+ (for local backend development)

## Quick Start

### 1. Clone and Setup

```bash
cd housing_analysis
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
# Required API Keys
OPENAI_API_KEY=sk-ant-xxxxx  # Get from https://platform.openai.com/api-keys
ZILLOW_API_KEY=xxxxx            # Get from RapidAPI
GREATSCHOOLS_API_KEY=xxxxx      # Get from GreatSchools API
GOOGLE_PLACES_API_KEY=xxxxx     # Get from Google Cloud Console
```

### 3. Start with Docker Compose

```bash
docker-compose up --build
```

This will start:
- PostgreSQL on port 5432
- Redis on port 6379
- MinIO on ports 9000 (API) and 9001 (Console)
- Backend API on port 8000
- Celery worker
- Frontend on port 5173

### 4. Access the Application

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (admin/minioadmin)

## Development Setup

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Run Celery Worker (for async tasks)

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info
```

## Project Structure

```
housing_analysis/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/      # API endpoints
│   │   ├── services/              # Business logic
│   │   │   ├── data_collectors/   # External data sources
│   │   │   ├── llm_services/      # Claude AI integration
│   │   │   ├── scoring/           # Scoring engine
│   │   │   └── reporting/         # Report generation
│   │   ├── models/                # Database & Pydantic models
│   │   ├── database/              # DB connection & migrations
│   │   ├── tasks/                 # Celery tasks
│   │   └── utils/                 # Utilities
│   ├── tests/                     # Backend tests
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/            # React components
│   │   ├── pages/                 # Page components
│   │   ├── services/              # API client
│   │   └── types/                 # TypeScript types
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

### Properties

- `POST /api/v1/properties/analyze` - Start property analysis
- `GET /api/v1/properties/analysis/{id}/status` - Get analysis status
- `GET /api/v1/properties/analysis/{id}/report` - Get analysis report (JSON)
- `GET /api/v1/properties/analysis/{id}/report/pdf` - Download PDF report

### Health

- `GET /health` - Health check
- `GET /api/v1/health` - Detailed service health

## Database Schema

Key tables:
- `properties` - Property information
- `property_analyses` - Analysis results
- `property_images` - Property images
- `schools` - School data
- `api_usage_logs` - API cost tracking
- `api_cache` - Response caching

See `backend/database/schema.sql` for complete schema.

## Configuration

All configuration is done via environment variables (see `.env.example`).

Key settings:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` - Claude API key
- `LLM_MODEL` - Claude model to use (default: gpt-4o)
- `CACHE_TTL_HOURS` - Cache TTL (default: 24 hours)
- `MAX_IMAGES_PER_ANALYSIS` - Max images to analyze (default: 15)

## Cost Estimates

Based on 100 analyses per month:

- **Claude API**: ~$10-15/month ($0.10-0.15 per analysis)
- **Infrastructure**: ~$80-100/month (PostgreSQL, Redis, S3, Compute)
- **Data Collection**: $0 (web scraping - free but requires server resources)

**Total**: ~$90-115/month ($0.90-1.15 per analysis)

**Savings from Web Scraping**: ~$70-165/month compared to paid APIs!

## Analysis Pipeline

1. User submits property address
2. System validates and normalizes address
3. Check cache for recent analysis (< 24 hours)
4. If not cached:
   - Collect data from Zillow, GreatSchools, Google Places (parallel)
   - Download and process property images
   - Run Claude AI analyses (parallel):
     - Property condition (vision + text)
     - Location quality
     - School analysis
     - Investment value
   - Calculate weighted scores
   - Generate PDF + HTML report
   - Save to database and cache
5. Return results to user

## Testing

### Backend Tests

```bash
cd backend
pytest
pytest --cov=app tests/  # With coverage
```

### Frontend Tests

```bash
cd frontend
npm test
```

## Deployment

### Production Deployment Steps

1. Update `.env` with production values
2. Set `DEBUG=False`
3. Configure production database (managed PostgreSQL)
4. Configure production Redis (managed service)
5. Set up S3 bucket (replace MinIO)
6. Deploy with Docker Compose or Kubernetes
7. Set up SSL/TLS with nginx or load balancer
8. Configure monitoring (Sentry, Prometheus)

### Environment-Specific Configs

- Use environment variables for all secrets
- Never commit `.env` file
- Use managed services in production (RDS, ElastiCache, S3)

## Troubleshooting

### Docker Issues

```bash
# Clean rebuild
docker-compose down -v
docker-compose up --build

# View logs
docker-compose logs -f backend
docker-compose logs -f celery_worker
```

### Database Issues

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d housing_analysis

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

### Redis Issues

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Clear cache
docker-compose exec redis redis-cli FLUSHALL
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests
4. Run linters: `black .` and `flake8`
5. Submit pull request

## License

MIT License

## Support

For issues and questions:
- Create an issue on GitHub
- Check the documentation at `/docs`

## Roadmap

### Week 1: Foundation (Completed)
- [x] Project structure
- [x] Docker setup
- [x] Database schema
- [x] FastAPI skeleton
- [x] React frontend skeleton

### Week 2: Data Collection (Completed)
- [x] Base web scraper with rate limiting
- [x] Zillow scraper
- [x] Redfin scraper
- [x] GreatSchools scraper
- [x] Image download and processing service
- [x] Redis caching layer
- [x] Claude API client
- [x] Celery tasks for async processing

### Week 3: LLM Analysis (Completed)
- [x] Comprehensive prompt templates for all 4 categories
- [x] Property condition analyzer (Vision + text)
- [x] Location quality analyzer
- [x] School quality analyzer
- [x] Investment value analyzer
- [x] Hybrid scoring engine (LLM + rules)
- [x] Analysis orchestrator (full pipeline)

### Week 4: Reports & UI (Completed)
- [x] Chart visualizations (bar, gauge, radar charts)
- [x] PDF report generation with ReportLab
- [x] Full API integration
- [x] Frontend components (ScoreCard, Analysis, Report pages)
- [x] Real-time status polling
- [x] PDF download functionality
- [x] Complete end-to-end pipeline

### Week 5: Optimization
- [ ] Web scraping fallback
- [ ] Advanced caching
- [ ] Prompt optimization
- [ ] Performance tuning

### Week 6: Production
- [ ] Authentication
- [ ] Monitoring
- [ ] Documentation
- [ ] CI/CD
- [ ] Deployment

## Getting API Keys

### Anthropic Claude (Required)
1. Visit https://platform.openai.com/api-keys
2. Sign up for an account
3. Navigate to API Keys
4. Create a new key
5. Add to `.env` as `OPENAI_API_KEY`

### Data Collection Strategy

**We use web scraping instead of paid APIs** to keep costs low:

- **Zillow**: Web scraping with respectful rate limiting (2 sec delay)
- **Redfin**: Web scraping using their undocumented APIs
- **GreatSchools**: Web scraping (optional API if available)

**Important Scraping Guidelines**:
- Respects robots.txt
- Rate limited (2 seconds between requests)
- Automatic retry with exponential backoff
- User-Agent identification
- Caches responses for 24 hours

**Legal Compliance**:
- Only scrapes publicly available data
- Implements rate limiting to avoid server overload
- Caches aggressively to minimize requests
- Can be configured with longer delays if needed

---

**Note**: This is an MVP implementation. Many features are marked as TODO and will be implemented in subsequent weeks according to the roadmap.
