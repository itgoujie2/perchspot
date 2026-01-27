/**
 * API client for Housing Analysis backend
 */
import axios from 'axios'
import type {
  PropertyAnalysisRequest,
  PropertyAnalysisResponse,
  AnalysisStatusResponse,
  AnalysisReportResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
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

export default api
