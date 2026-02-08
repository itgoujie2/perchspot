import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  Chip,
  Divider,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
} from '@mui/material'
import { Download, CheckCircle, Warning } from '@mui/icons-material'
import api from '../services/api'
import ScoreCard from '../components/ScoreCard'
import type { AnalysisReportResponse } from '../types'

export default function Report() {
  const { id } = useParams<{ id: string }>()
  const [report, setReport] = useState<AnalysisReportResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return

    const fetchReport = async () => {
      try {
        const data = await api.getAnalysisReport(id)
        setReport(data)
        setLoading(false)
      } catch (err: any) {
        console.error('Error fetching report:', err)
        setError('Failed to load analysis report')
        setLoading(false)
      }
    }

    fetchReport()
  }, [id])

  const handleDownloadPDF = async () => {
    try {
      const blob = await api.downloadPDFReport(id!)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `property_report_${id?.slice(0, 8)}.pdf`
      link.click()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Error downloading PDF:', err)
      alert('Failed to download PDF')
    }
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error || !report) {
    return (
      <Box sx={{ mt: 8 }}>
        <Alert severity="error">{error || 'Report not found'}</Alert>
      </Box>
    )
  }

  return (
    <Box sx={{ mt: 4, mb: 8 }}>
      {/* Header */}
      <Paper sx={{ p: 4, mb: 3, bgcolor: 'primary.main', color: 'white' }}>
        <Typography variant="h3" gutterBottom>
          Property Analysis Report
        </Typography>
        <Typography variant="h5" sx={{ mb: 2 }}>
          {report.property_data.address}
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <Chip
            label={`Grade: ${report.overall_grade}`}
            sx={{ bgcolor: 'white', color: 'primary.main', fontSize: '1.2rem', fontWeight: 'bold', height: 40, '& .MuiChip-label': { px: 2 } }}
            size="medium"
          />
          <Chip
            label={`Confidence: ${report.confidence}`}
            sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
          />
          <Button
            variant="contained"
            color="secondary"
            startIcon={<Download />}
            onClick={handleDownloadPDF}
            sx={{ ml: 'auto' }}
          >
            Download PDF
          </Button>
        </Box>
      </Paper>

      {/* Overall Score */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12}>
          <ScoreCard title="Overall Score" score={Number(report.overall_score)} />
        </Grid>
      </Grid>

      {/* Category Scores */}
      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
        Category Scores
      </Typography>
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <ScoreCard
            title="Property Condition"
            score={Number(report.category_scores.property_condition)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <ScoreCard
            title="Location Quality"
            score={Number(report.category_scores.location_quality)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <ScoreCard
            title="Schools"
            score={Number(report.category_scores.schools)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <ScoreCard
            title="Investment Value"
            score={Number(report.category_scores.investment_value)}
          />
        </Grid>
      </Grid>

      {/* Detailed Analysis */}
      <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 2 }}>
        Detailed Analysis
      </Typography>

      {/* Property Condition */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom color="primary">
            Property Condition
          </Typography>
          <Typography variant="body1" paragraph>
            {report.detailed_analysis.property_condition.reasoning}
          </Typography>

          {report.detailed_analysis.property_condition.highlights.length > 0 && (
            <>
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                <CheckCircle sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'text-bottom' }} />
                Highlights
              </Typography>
              <List dense>
                {report.detailed_analysis.property_condition.highlights.map((item, idx) => (
                  <ListItem key={idx}>
                    <ListItemText primary={`• ${item}`} />
                  </ListItem>
                ))}
              </List>
            </>
          )}

          {report.detailed_analysis.property_condition.concerns.length > 0 && (
            <>
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                <Warning sx={{ fontSize: 16, mr: 0.5, verticalAlign: 'text-bottom' }} />
                Concerns
              </Typography>
              <List dense>
                {report.detailed_analysis.property_condition.concerns.map((item, idx) => (
                  <ListItem key={idx}>
                    <ListItemText primary={`• ${item}`} />
                  </ListItem>
                ))}
              </List>
            </>
          )}
        </CardContent>
      </Card>

      {/* Location Quality */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom color="primary">
            Location Quality
          </Typography>
          <Typography variant="body1" paragraph>
            {report.detailed_analysis.location_quality.reasoning}
          </Typography>

          {report.detailed_analysis.location_quality.nearby_amenities.length > 0 && (
            <>
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                Nearby Amenities
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {report.detailed_analysis.location_quality.nearby_amenities.map((item, idx) => (
                  <Chip key={idx} label={item} size="small" />
                ))}
              </Box>
            </>
          )}
        </CardContent>
      </Card>

      {/* Schools */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom color="primary">
            Schools
          </Typography>
          <Typography variant="body1" paragraph>
            {report.detailed_analysis.schools.reasoning}
          </Typography>

          {report.detailed_analysis.schools.schools.length > 0 && (
            <>
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                Nearby Schools
              </Typography>
              <List>
                {report.detailed_analysis.schools.schools.map((school, idx) => (
                  <ListItem key={idx}>
                    <ListItemText
                      primary={school.name}
                      secondary={`${school.school_type} | Rating: ${school.rating}/10 | Distance: ${school.distance_miles} miles`}
                    />
                  </ListItem>
                ))}
              </List>
            </>
          )}
        </CardContent>
      </Card>

      {/* Investment Value */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom color="primary">
            Investment Value
          </Typography>
          <Typography variant="body1" paragraph>
            {report.detailed_analysis.investment_value.reasoning}
          </Typography>

          {report.detailed_analysis.investment_value.recommendations && (
            <>
              <Typography variant="subtitle1" gutterBottom sx={{ mt: 2 }}>
                Recommendations
              </Typography>
              <List dense>
                {report.detailed_analysis.investment_value.recommendations.map((item, idx) => (
                  <ListItem key={idx}>
                    <ListItemText primary={`• ${item}`} />
                  </ListItem>
                ))}
              </List>
            </>
          )}
        </CardContent>
      </Card>

      {/* Property Details */}
      <Divider sx={{ my: 4 }} />
      <Typography variant="h6" gutterBottom>
        Property Details
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Price</Typography>
          <Typography variant="body1">${report.property_data.price?.toLocaleString() || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Bedrooms</Typography>
          <Typography variant="body1">{report.property_data.bedrooms || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Bathrooms</Typography>
          <Typography variant="body1">{report.property_data.bathrooms || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Square Feet</Typography>
          <Typography variant="body1">{report.property_data.square_feet?.toLocaleString() || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Year Built</Typography>
          <Typography variant="body1">{report.property_data.year_built || 'N/A'}</Typography>
        </Grid>
        <Grid item xs={6} sm={4}>
          <Typography variant="body2" color="text.secondary">Property Type</Typography>
          <Typography variant="body1">{report.property_data.property_type || 'N/A'}</Typography>
        </Grid>
      </Grid>
    </Box>
  )
}
