/**
 * TypeScript type definitions for the Perchspot application
 */

export enum AnalysisStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum ConfidenceLevel {
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
}

export interface PropertyAnalysisRequest {
  address: string
}

export interface PropertyAnalysisResponse {
  analysis_id: string
  status: AnalysisStatus
  message: string
}

export interface AnalysisStatusResponse {
  analysis_id: string
  status: AnalysisStatus
  progress: number
  current_step?: string
  estimated_time_remaining?: number
  error_message?: string
}

export interface CategoryScores {
  property_condition: number
  location_quality: number
  schools: number
  investment_value: number
}

export interface PropertyConditionAnalysis {
  score: number
  sub_scores?: {
    exterior?: number
    interior?: number
    kitchen_bath?: number
    systems?: number
  }
  reasoning: string
  highlights: string[]
  concerns: string[]
  confidence: ConfidenceLevel
}

export interface LocationQualityAnalysis {
  score: number
  neighborhood_score?: number
  amenities_score?: number
  transit_score?: number
  walkability_score?: number
  reasoning: string
  nearby_amenities: string[]
  transit_options: string[]
  confidence: ConfidenceLevel
}

export interface SchoolAnalysis {
  score: number
  schools: Array<{
    name: string
    school_type: string
    rating?: number
    distance_miles?: number
  }>
  reasoning: string
  highlights: string[]
  concerns: string[]
  confidence: ConfidenceLevel
}

export interface InvestmentValueAnalysis {
  score: number
  price_vs_market?: number
  appreciation_potential?: string
  rental_yield_estimate?: number
  market_trends?: string
  reasoning: string
  recommendations: string[]
  confidence: ConfidenceLevel
}

export interface DetailedAnalysis {
  property_condition: PropertyConditionAnalysis
  location_quality: LocationQualityAnalysis
  schools: SchoolAnalysis
  investment_value: InvestmentValueAnalysis
}

export interface PropertyData {
  id?: string
  address: string
  city?: string
  state?: string
  zip_code?: string
  price?: number
  bedrooms?: number
  bathrooms?: number
  square_feet?: number
  year_built?: number
  property_type?: string
  description?: string
}

export interface AnalysisReportResponse {
  analysis_id: string
  overall_score: number
  overall_grade: string
  confidence: ConfidenceLevel
  category_scores: CategoryScores
  detailed_analysis: DetailedAnalysis
  property_data: PropertyData
  images: Array<{
    id: string
    image_url?: string
    storage_path?: string
    image_type: string
    caption?: string
  }>
  analyzed_at: string
  llm_model?: string
  processing_time_seconds?: number
}

// Document upload types
export type DocumentType = 'inspection' | 'hoa' | 'unknown'

export interface DocumentUploadResponse {
  status: 'accepted' | 'error'
  job_id: string
  document_type: DocumentType
  address: string
  message?: string
  credit_balance?: number
}

export interface DocumentStatusResponse {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  document_type: DocumentType
  result?: DocumentAnalysisResult
  error?: string
  credit_balance?: number
}

export interface DocumentAnalysisResult {
  score: number
  confidence: string
  reasoning: string
  strengths: string[]
  concerns: string[]
  details: Record<string, any>
}

export interface PropertyDocument {
  id: string
  document_type: DocumentType
  filename: string
  uploaded_at: string
  summary?: string
  score?: number
}

export interface PropertyDocumentsResponse {
  address: string
  documents: PropertyDocument[]
}

// Inspection-specific types
export interface InspectionIssue {
  system: string
  description: string
  severity: 'safety' | 'major' | 'moderate' | 'minor' | 'cosmetic'
  estimated_cost: string
  urgency: string
}

export interface InspectionAnalysisDetails {
  issues: InspectionIssue[]
  total_estimated_repairs: string
  immediate_repairs?: string
  deferred_maintenance?: string
  systems_summary?: Record<string, string>
}

// HOA-specific types
export interface HOAAnalysisDetails {
  monthly_fee?: number
  fee_includes?: string[]
  reserve_fund?: {
    funded_percentage?: number
    balance?: number
    assessment?: string
  }
  rental_restrictions?: {
    allowed?: boolean
    minimum_lease?: string
    cap?: string | null
    waiting_period?: string | null
  }
  pet_restrictions?: {
    allowed?: boolean
    size_limit?: string
    breed_restrictions?: boolean
    max_pets?: number
  }
  special_assessments?: Array<{
    year: number
    amount: number
    purpose: string
  }>
  litigation?: {
    pending: boolean
    history?: string | null
  }
}

// Favorites types
export interface Favorite {
  id: string
  address: string
  nickname?: string
  notes?: string
  created_at: string
}

export interface FavoritesListResponse {
  favorites: Favorite[]
  total: number
}

export interface AddFavoriteRequest {
  address: string
  nickname?: string
  notes?: string
}

export interface CheckFavoriteResponse {
  is_favorite: boolean
  favorite_id?: string
}

// History types
export interface HistoryItem {
  id: string
  address: string
  analyzed_at: string
  cost: number
}

export interface HistoryListResponse {
  items: HistoryItem[]
  total: number
}

// Compare types
export interface PropertyScores {
  property?: number
  location?: number
  schools?: number
  investment?: number
  overall?: number
}

export interface PropertySummary {
  address: string
  price?: string
  beds?: number
  baths?: number
  sqft?: number
  year_built?: number
  scores: PropertyScores
  strengths: string[]
  concerns: string[]
  cached: boolean
  needs_analysis?: boolean
}

export interface CompareRequest {
  addresses: string[]
}

export interface CompareResponse {
  properties: PropertySummary[]
  comparison_notes?: string
}
