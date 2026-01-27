import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  CircularProgress,
  LinearProgress,
  Paper,
  Alert,
} from '@mui/material'
import api from '../services/api'
import type { AnalysisStatusResponse } from '../types'

export default function Analysis() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<AnalysisStatusResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return

    // Poll for status updates
    const pollInterval = setInterval(async () => {
      try {
        const statusData = await api.getAnalysisStatus(id)
        setStatus(statusData)

        // If completed, navigate to report
        if (statusData.status === 'completed') {
          clearInterval(pollInterval)
          setTimeout(() => {
            navigate(`/report/${id}`)
          }, 1000)
        }

        // If failed, show error
        if (statusData.status === 'failed') {
          clearInterval(pollInterval)
          setError(statusData.error_message || 'Analysis failed')
        }
      } catch (err: any) {
        console.error('Error polling status:', err)
        setError('Failed to check analysis status')
        clearInterval(pollInterval)
      }
    }, 2000) // Poll every 2 seconds

    return () => clearInterval(pollInterval)
  }, [id, navigate])

  return (
    <Box sx={{ mt: 8 }}>
      <Typography variant="h4" gutterBottom>
        Analysis in Progress
      </Typography>

      <Paper sx={{ p: 4, mt: 3 }}>
        {error ? (
          <Alert severity="error">{error}</Alert>
        ) : (
          <>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CircularProgress sx={{ mr: 2 }} />
              <Typography variant="h6">
                {status?.current_step || 'Initializing...'}
              </Typography>
            </Box>

            <LinearProgress
              variant="determinate"
              value={status?.progress || 0}
              sx={{ mt: 2 }}
            />

            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              Progress: {status?.progress || 0}%
            </Typography>

            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Analysis ID: {id}
            </Typography>

            <Typography variant="body2" sx={{ mt: 2 }}>
              This typically takes 30-60 seconds. Please wait...
            </Typography>
          </>
        )}
      </Paper>
    </Box>
  )
}
