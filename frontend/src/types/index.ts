/**
 * TypeScript type definitions for the Housing Analysis application
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
