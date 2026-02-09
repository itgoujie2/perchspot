import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Logo from '../assets/logo.svg'
import SEOHead from '../components/SEOHead'
import StructuredData from '../components/StructuredData'
import './Home.css'

export default function Home() {
  const [address, setAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!address.trim()) return
    setLoading(true)
    navigate(`/chat?address=${encodeURIComponent(address)}`)
  }

  return (
    <div className="landing-page">
      <SEOHead
        title="Perchspot - AI-Powered Home Analysis"
        description="Get instant AI analysis of any property. Evaluate condition, schools, investment potential, and location quality with Perchspot."
        path="/"
      />
      <StructuredData data={{
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Perchspot",
        "description": "AI-powered property analysis platform",
        "url": "https://perchspot.com",
        "applicationCategory": "RealEstateApplication",
        "operatingSystem": "Web Browser"
      }} />

      <div className="landing-card">
        <img src={Logo} alt="Perchspot" className="logo" />
        <p className="tagline">AI-powered property reports in minutes</p>

        {error && (
          <div className="error-alert">
            <span>{error}</span>
            <button onClick={() => setError(null)}>&times;</button>
          </div>
        )}

        <form className="search-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="Enter a property address..."
            required
            disabled={loading}
          />
          <button type="submit" disabled={loading || !address.trim()}>
            {loading ? '...' : '\u2192'}
          </button>
        </form>
      </div>

      <div className="feature-grid">
        <div className="feature-card">
          <div className="feature-icon">🏠</div>
          <h3>Property</h3>
          <p>Condition scoring, features, and maintenance outlook</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">📍</div>
          <h3>Location</h3>
          <p>Walkability, transit, and neighborhood quality</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🎓</div>
          <h3>Schools</h3>
          <p>Nearby school ratings, types, and distances</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">💰</div>
          <h3>Investment</h3>
          <p>Market analysis, pricing, and appreciation potential</p>
        </div>
      </div>
    </div>
  )
}
