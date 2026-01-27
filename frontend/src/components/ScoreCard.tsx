import { Box, Card, CardContent, Typography, LinearProgress } from '@mui/material'

interface ScoreCardProps {
  title: string
  score: number
  maxScore?: number
}

export default function ScoreCard({ title, score, maxScore = 100 }: ScoreCardProps) {
  const percentage = (score / maxScore) * 100

  const getColor = (score: number) => {
    if (score >= 90) return 'success.main'
    if (score >= 80) return 'info.main'
    if (score >= 70) return 'warning.light'
    if (score >= 60) return 'warning.main'
    return 'error.main'
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 1 }}>
          <Typography variant="h3" component="span" sx={{ color: getColor(score) }}>
            {score.toFixed(0)}
          </Typography>
          <Typography variant="h5" component="span" sx={{ ml: 1, color: 'text.secondary' }}>
            / {maxScore}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={percentage}
          sx={{
            height: 10,
            borderRadius: 5,
            backgroundColor: 'grey.200',
            '& .MuiLinearProgress-bar': {
              backgroundColor: getColor(score)
            }
          }}
        />
      </CardContent>
    </Card>
  )
}
