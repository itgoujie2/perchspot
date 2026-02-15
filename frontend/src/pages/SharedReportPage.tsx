import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { shareApi, SharedReportResponse } from '../services/api';
import Logo from '../assets/logo.svg';
import SEOHead from '../components/SEOHead';
import './SharedReportPage.css';

// Helper to safely get nested values
const get = (obj: any, path: string, fallback: any = undefined) => {
  return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : fallback), obj);
};

const formatPrice = (n: any) => {
  if (!n) return '—';
  const num = typeof n === 'string' ? parseFloat(n.replace(/[^0-9.]/g, '')) : n;
  if (isNaN(num)) return String(n);
  return '$' + num.toLocaleString();
};

const getGrade = (score: number | null): string | null => {
  if (score === null) return null;
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
};

const getRiskColor = (level: string) => {
  const l = (level || '').toLowerCase();
  if (l.includes('low') || l.includes('minimal') || l.includes('none')) return '#4caf50';
  if (l.includes('moderate') || l.includes('medium')) return '#ff9800';
  return '#f44336';
};

// Circular score indicator
const ScoreCircle: React.FC<{ value: number; label: string; max?: number }> = ({ value, label, max = 100 }) => {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const r = 30;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="score-circle">
      <svg width="76" height="76" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={r} fill="none" stroke="#e0e0e0" strokeWidth="6" />
        <circle cx="38" cy="38" r={r} fill="none" stroke="#667eea" strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 38 38)" />
        <text x="38" y="42" textAnchor="middle" fontSize="14" fontWeight="600" fill="#333">{value}</text>
      </svg>
      <span className="score-label">{label}</span>
    </div>
  );
};

// Score bar for analysis sections
const ScoreBar: React.FC<{ score: number; max?: number }> = ({ score, max = 100 }) => {
  const pct = Math.min(100, Math.round((score / max) * 100));
  const color = pct >= 70 ? '#4caf50' : pct >= 40 ? '#ff9800' : '#f44336';
  return (
    <div className="score-bar-container">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="score-bar-value">{score}/{max}</span>
    </div>
  );
};

const SharedReportPage: React.FC = () => {
  const { shareCode } = useParams<{ shareCode: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<SharedReportResponse | null>(null);

  useEffect(() => {
    const fetchReport = async () => {
      if (!shareCode) {
        setError('Invalid share link');
        setLoading(false);
        return;
      }

      try {
        const data = await shareApi.get(shareCode);
        setReport(data);
      } catch (err: any) {
        if (err.response?.status === 404) {
          setError('This shared report was not found.');
        } else if (err.response?.status === 410) {
          setError('This shared link has expired.');
        } else {
          setError('Failed to load shared report.');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchReport();
  }, [shareCode]);

  if (loading) {
    return (
      <div className="shared-report-page">
        <div className="shared-loading">
          <div className="spinner"></div>
          <p>Loading report...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="shared-report-page">
        <SEOHead title="Shared Report - Perchspot" description="View shared property analysis" path={`/share/${shareCode}`} />
        <div className="shared-error">
          <h2>Report Not Found</h2>
          <p>{error}</p>
          <Link to="/" className="btn-primary">Analyze Your Own Property</Link>
        </div>
      </div>
    );
  }

  const data = report.report_data;
  const address = report.address;

  // Extract data from report
  const property = data.property || data.details || {};
  const pricing = data.pricing || {};
  const schools = data.schools || [];
  const location = data.location || {};
  const climate = data.climate_risks || data.climate || {};
  const images = data.images || {};

  // Analysis results
  const analysisResults = data.analysis_results || {};
  const propAnalysis = analysisResults.property || {};
  const locAnalysis = analysisResults.location || {};
  const schoolAnalysis = analysisResults.schools || {};
  const investmentAnalysis = analysisResults.investment || {};

  // Scores
  const propScore = propAnalysis.score || null;
  const locScore = locAnalysis.score || null;
  const schoolScore = schoolAnalysis.score || null;
  const investmentScore = investmentAnalysis.score || null;
  const scoreParts = [propScore, locScore, schoolScore, investmentScore].filter((s): s is number => s !== null);
  const overallScore = scoreParts.length > 0 ? Math.round(scoreParts.reduce((a, b) => a + b, 0) / scoreParts.length) : null;

  return (
    <div className="shared-report-page">
      <SEOHead
        title={`${address} - Property Analysis | Perchspot`}
        description={`AI-powered property analysis for ${address}. Score: ${overallScore || 'N/A'}/100`}
        path={`/share/${shareCode}`}
      />

      <header className="shared-header">
        <Link to="/" className="logo-link">
          <img src={Logo} alt="Perchspot" className="header-logo" />
        </Link>
        <div className="header-cta">
          <Link to="/" className="btn-primary">Analyze Your Property</Link>
        </div>
      </header>

      <main className="shared-content">
        <div className="report-container">
          <div className="report-title">
            <h1>Property Report</h1>
            <p className="report-address">{address}</p>
            <p className="report-meta">Shared report • {report.view_count} views</p>
          </div>

          {/* Overall Score */}
          {overallScore !== null && (
            <div className="report-section report-overall">
              <div className="overall-score-row">
                <ScoreCircle value={overallScore} label="Overall" />
                {propScore !== null && <ScoreCircle value={propScore} label="Property" />}
                {locScore !== null && <ScoreCircle value={locScore} label="Location" />}
                {schoolScore !== null && <ScoreCircle value={schoolScore} label="Schools" />}
                {investmentScore !== null && <ScoreCircle value={investmentScore} label="Investment" />}
              </div>
            </div>
          )}

          {/* Property Photo */}
          {images.main_photo_url && (
            <div className="report-section">
              <img src={images.main_photo_url} alt={address} className="property-main-photo" />
            </div>
          )}

          {/* Property Overview */}
          <div className="report-section property-overview">
            <h4>Property Overview</h4>
            <div className="property-header-row">
              <span className="property-price">{formatPrice(get(pricing, 'list_price') || get(property, 'price'))}</span>
              {get(property, 'status') && <span className="status-badge">{get(property, 'status')}</span>}
            </div>
            <div className="property-details-row">
              {get(property, 'bedrooms') && <span>{get(property, 'bedrooms')} beds</span>}
              {get(property, 'bathrooms') && <span>{get(property, 'bathrooms')} baths</span>}
              {get(property, 'living_area_sqft') && <span>{Number(get(property, 'living_area_sqft')).toLocaleString()} sqft</span>}
              {get(property, 'year_built') && <span>Built {get(property, 'year_built')}</span>}
            </div>
          </div>

          {/* Pricing */}
          {Object.keys(pricing).length > 0 && (
            <div className="report-section">
              <h4>Pricing</h4>
              <table className="report-table">
                <tbody>
                  {pricing.list_price && <tr><td>List Price</td><td>{formatPrice(pricing.list_price)}</td></tr>}
                  {pricing.redfin_estimate && <tr><td>Estimated Value</td><td>{formatPrice(pricing.redfin_estimate)}</td></tr>}
                  {pricing.rental_estimate && <tr><td>Rental Estimate</td><td>{formatPrice(pricing.rental_estimate)}/mo</td></tr>}
                  {pricing.price_per_sqft && <tr><td>Price/sqft</td><td>{formatPrice(pricing.price_per_sqft)}</td></tr>}
                </tbody>
              </table>
            </div>
          )}

          {/* Schools */}
          {schools.length > 0 && (
            <div className="report-section">
              <h4>Schools</h4>
              <table className="report-table schools-table">
                <thead>
                  <tr><th>School</th><th>Type</th><th>Rating</th></tr>
                </thead>
                <tbody>
                  {schools.slice(0, 5).map((s: any, i: number) => (
                    <tr key={i}>
                      <td>{s.name || '—'}</td>
                      <td>{s.type || '—'}</td>
                      <td>{s.rating || '—'}/10</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Location Scores */}
          {(location.walkability_score || location.transit_score || location.bike_score) && (
            <div className="report-section">
              <h4>Location Scores</h4>
              <div className="scores-row">
                {location.walkability_score && <ScoreCircle value={location.walkability_score} label="Walk" />}
                {location.transit_score && <ScoreCircle value={location.transit_score} label="Transit" />}
                {location.bike_score && <ScoreCircle value={location.bike_score} label="Bike" />}
              </div>
            </div>
          )}

          {/* Climate Risks */}
          {Object.keys(climate).length > 0 && (
            <div className="report-section">
              <h4>Climate Risks</h4>
              <div className="risk-chips">
                {Object.entries(climate)
                  .filter(([k]) => k !== 'air_quality')
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className="risk-chip"
                      style={{
                        background: getRiskColor(String(v)) + '22',
                        color: getRiskColor(String(v)),
                        borderColor: getRiskColor(String(v))
                      }}
                    >
                      {k}: {String(v)}
                    </span>
                  ))}
              </div>
            </div>
          )}

          {/* Analysis Sections */}
          {propAnalysis.score && (
            <div className="report-section">
              <h4>Property Condition</h4>
              <ScoreBar score={propAnalysis.score} />
              {propAnalysis.strengths?.length > 0 && (
                <div className="analysis-list">
                  <strong>Strengths</strong>
                  <ul>{propAnalysis.strengths.slice(0, 3).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
              {propAnalysis.concerns?.length > 0 && (
                <div className="analysis-list">
                  <strong>Concerns</strong>
                  <ul>{propAnalysis.concerns.slice(0, 3).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {locAnalysis.score && (
            <div className="report-section">
              <h4>Location Quality</h4>
              <ScoreBar score={locAnalysis.score} />
              {locAnalysis.strengths?.length > 0 && (
                <div className="analysis-list">
                  <strong>Strengths</strong>
                  <ul>{locAnalysis.strengths.slice(0, 3).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {investmentAnalysis.score && (
            <div className="report-section">
              <h4>Investment Potential</h4>
              <ScoreBar score={investmentAnalysis.score} />
              {investmentAnalysis.strengths?.length > 0 && (
                <div className="analysis-list">
                  <strong>Strengths</strong>
                  <ul>{investmentAnalysis.strengths.slice(0, 3).map((s: string, i: number) => <li key={i}>{s}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {/* CTA */}
          <div className="report-cta">
            <h3>Want to analyze your own property?</h3>
            <p>Get AI-powered insights on any property in seconds.</p>
            <Link to="/" className="btn-primary btn-large">Start Free Analysis</Link>
          </div>
        </div>
      </main>

      <footer className="shared-footer">
        <p>Powered by <a href="https://perchspot.com">Perchspot</a> - AI-Powered Property Analysis</p>
      </footer>
    </div>
  );
};

export default SharedReportPage;
