/**
 * API client for Perchspot backend
 */
import axios from 'axios'
import type {
  PropertyAnalysisRequest,
  PropertyAnalysisResponse,
  AnalysisStatusResponse,
  AnalysisReportResponse,
  DocumentUploadResponse,
  DocumentStatusResponse,
  PropertyDocumentsResponse,
  DocumentType,
  FavoritesListResponse,
  Favorite,
  AddFavoriteRequest,
  CheckFavoriteResponse,
  HistoryListResponse,
  CompareRequest,
  CompareResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Attach JWT token to all requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const api = {
  /**
   * Request property analysis
   */
  analyzeProperty: async (
    request: PropertyAnalysisRequest
  ): Promise<PropertyAnalysisResponse> => {
    const response = await apiClient.post('/properties/analyze', request)
    return response.data
  },

  /**
   * Get analysis status
   */
  getAnalysisStatus: async (
    analysisId: string
  ): Promise<AnalysisStatusResponse> => {
    const response = await apiClient.get(
      `/properties/analysis/${analysisId}/status`
    )
    return response.data
  },

  /**
   * Get analysis report
   */
  getAnalysisReport: async (
    analysisId: string
  ): Promise<AnalysisReportResponse> => {
    const response = await apiClient.get(
      `/properties/analysis/${analysisId}/report`
    )
    return response.data
  },

  /**
   * Download PDF report
   */
  downloadPDFReport: async (analysisId: string): Promise<Blob> => {
    const response = await apiClient.get(
      `/properties/analysis/${analysisId}/report/pdf`,
      {
        responseType: 'blob',
      }
    )
    return response.data
  },

  /**
   * Health check
   */
  healthCheck: async (): Promise<any> => {
    const response = await apiClient.get('/health')
    return response.data
  },
}

export const authApi = {
  register: async (email: string, password: string) => {
    const response = await apiClient.post('/auth/register', { email, password })
    return response.data
  },

  login: async (email: string, password: string) => {
    const response = await apiClient.post('/auth/login', { email, password })
    return response.data
  },

  me: async () => {
    const response = await apiClient.get('/auth/me')
    return response.data
  },
}

export const promotionsApi = {
  /**
   * Get promotion status (survey completion, etc.)
   */
  getStatus: async () => {
    const response = await apiClient.get('/promotions/status')
    return response.data
  },

  /**
   * Complete feedback survey and claim reward
   */
  completeSurvey: async () => {
    const response = await apiClient.post('/promotions/survey-complete')
    return response.data
  },
}

export const referralsApi = {
  /**
   * Get user's referral code (creates if doesn't exist)
   */
  getMyCode: async () => {
    const response = await apiClient.get('/referrals/my-code')
    return response.data
  },

  /**
   * Get referral statistics
   */
  getStats: async () => {
    const response = await apiClient.get('/referrals/stats')
    return response.data
  },
}

export const documentsApi = {
  /**
   * Upload a document for analysis
   */
  uploadDocument: async (
    address: string,
    file: File,
    documentType: DocumentType | 'auto' = 'auto'
  ): Promise<DocumentUploadResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)

    const response = await apiClient.post(
      `/documents/upload/${encodeURIComponent(address)}`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
    return response.data
  },

  /**
   * Check document analysis status
   */
  getDocumentStatus: async (jobId: string): Promise<DocumentStatusResponse> => {
    const response = await apiClient.get(`/documents/status/${jobId}`)
    return response.data
  },

  /**
   * Get all documents for a property
   */
  getPropertyDocuments: async (
    address: string
  ): Promise<PropertyDocumentsResponse> => {
    const response = await apiClient.get(
      `/documents/${encodeURIComponent(address)}`
    )
    return response.data
  },

  /**
   * Poll for document analysis completion
   */
  waitForCompletion: async (
    jobId: string,
    pollInterval = 1000,
    maxAttempts = 120
  ): Promise<DocumentStatusResponse> => {
    for (let i = 0; i < maxAttempts; i++) {
      const status = await documentsApi.getDocumentStatus(jobId)
      if (status.status === 'completed' || status.status === 'failed') {
        return status
      }
      await new Promise((resolve) => setTimeout(resolve, pollInterval))
    }
    throw new Error('Document analysis timed out')
  },
}

export const favoritesApi = {
  /**
   * List all user's favorites
   */
  list: async (): Promise<FavoritesListResponse> => {
    const response = await apiClient.get('/favorites')
    return response.data
  },

  /**
   * Add a property to favorites
   */
  add: async (request: AddFavoriteRequest): Promise<Favorite> => {
    const response = await apiClient.post('/favorites', request)
    return response.data
  },

  /**
   * Check if address is in favorites
   */
  check: async (address: string): Promise<CheckFavoriteResponse> => {
    const response = await apiClient.get('/favorites/check', {
      params: { address },
    })
    return response.data
  },

  /**
   * Update favorite nickname/notes
   */
  update: async (
    favoriteId: string,
    data: { nickname?: string; notes?: string }
  ): Promise<Favorite> => {
    const response = await apiClient.patch(`/favorites/${favoriteId}`, data)
    return response.data
  },

  /**
   * Remove from favorites
   */
  remove: async (favoriteId: string): Promise<void> => {
    await apiClient.delete(`/favorites/${favoriteId}`)
  },
}

export const historyApi = {
  /**
   * Get analysis history
   */
  list: async (limit = 50, offset = 0): Promise<HistoryListResponse> => {
    const response = await apiClient.get('/history', {
      params: { limit, offset },
    })
    return response.data
  },
}

export const compareApi = {
  /**
   * Compare 2-3 properties
   */
  compare: async (request: CompareRequest): Promise<CompareResponse> => {
    const response = await apiClient.post('/compare', request)
    return response.data
  },
}

export default api
