import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  Container,
  Alert,
} from '@mui/material'
import { Search } from '@mui/icons-material'
import api from '../services/api'

export default function Home() {
  const [address, setAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      // Navigate to chat page with address as query parameter for streaming analysis
      navigate(`/chat?address=${encodeURIComponent(address)}`)
    } catch (err: any) {
      console.error('Error starting analysis:', err)
      setError(err.response?.data?.detail || 'Failed to start analysis. Please try again.')
      setLoading(false)
    }
  }

  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Typography variant="h2" component="h1" gutterBottom align="center">
          Housing Analysis
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom align="center" color="text.secondary">
          AI-Powered Property Analysis
        </Typography>
      </Box>

      <Paper elevation={3} sx={{ p: 4, mt: 4 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Property Address"
            variant="outlined"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="123 Main St, San Francisco, CA 94102"
            required
            sx={{ mb: 3 }}
            disabled={loading}
          />

          <Button
            type="submit"
            variant="contained"
            size="large"
            fullWidth
            disabled={loading || !address}
            startIcon={<Search />}
          >
            {loading ? 'Starting Analysis...' : 'Analyze Property'}
          </Button>
        </form>

        <Box sx={{ mt: 4 }}>
          <Typography variant="h6" gutterBottom>
            What We Analyze:
          </Typography>
          <Typography variant="body2" paragraph>
            • <strong>Property Condition (30%)</strong> - Detailed analysis of property state using AI vision
          </Typography>
          <Typography variant="body2" paragraph>
            • <strong>Location Quality (25%)</strong> - Neighborhood, amenities, and transportation access
          </Typography>
          <Typography variant="body2" paragraph>
            • <strong>Schools (20%)</strong> - Quality and proximity of educational institutions
          </Typography>
          <Typography variant="body2" paragraph>
            • <strong>Investment Value (25%)</strong> - Market analysis and ROI potential
          </Typography>
        </Box>
      </Paper>
    </Container>
  )
}
