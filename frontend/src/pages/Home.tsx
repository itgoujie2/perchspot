import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
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
          <div className="feature-icon">⚡</div>
          <h3>Instant Analysis</h3>
          <p>Get comprehensive property reports in under 2 minutes</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🎯</div>
          <h3>Unbiased Insights</h3>
          <p>AI-powered analysis with no sales pressure or hidden agenda</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">📊</div>
          <h3>Data-Driven Scores</h3>
          <p>Clear 0-100 ratings across property, location, schools, and investment</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">☕</div>
          <h3>Cheaper Than Coffee</h3>
          <p>Full property analysis for less than a latte—no subscriptions needed</p>
        </div>
      </div>

      <footer className="landing-footer">
        <Link to="/blog">Home Buying Guides</Link>
        <span className="footer-divider">·</span>
        <Link to="/compare">Compare Properties</Link>
      </footer>
    </div>
  )
}
