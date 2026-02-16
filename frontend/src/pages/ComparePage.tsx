import React, { useState, useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { compareApi } from '../services/api';
import type { PropertySummary, CompareResponse } from '../types';
import Logo from '../assets/logo.svg';
import SEOHead from '../components/SEOHead';
import './ComparePage.css';

const ComparePage: React.FC = () => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [addresses, setAddresses] = useState<string[]>(['', '']);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const autoCompareTriggered = useRef(false);

  // Load addresses from URL params on mount
  useEffect(() => {
    const addressParam = searchParams.get('addresses');
    if (addressParam) {
      const parsedAddresses = addressParam.split(',').map(a => decodeURIComponent(a.trim())).filter(a => a);
      if (parsedAddresses.length >= 2) {
        setAddresses(parsedAddresses);
      }
    }
  }, [searchParams]);

  // Auto-compare when addresses loaded from URL
  useEffect(() => {
    const validAddresses = addresses.filter(a => a.trim());
    if (validAddresses.length >= 2 && !result && !loading && !autoCompareTriggered.current) {
      const addressParam = searchParams.get('addresses');
      if (addressParam) {
        autoCompareTriggered.current = true;
        handleCompare();
      }
    }
  }, [addresses]);

  const handleAddressChange = (index: number, value: string) => {
    const newAddresses = [...addresses];
    newAddresses[index] = value;
    setAddresses(newAddresses);
  };

  const addAddress = () => {
    if (addresses.length < 3) {
      setAddresses([...addresses, '']);
    }
  };

  const removeAddress = (index: number) => {
    if (addresses.length > 2) {
      setAddresses(addresses.filter((_, i) => i !== index));
    }
  };

  const handleCompare = async () => {
    const validAddresses = addresses.filter((a) => a.trim());
    if (validAddresses.length < 2) {
      setError('Please enter at least 2 addresses');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await compareApi.compare({ addresses: validAddresses });
      setResult(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number | undefined) => {
    if (score === undefined) return '#94a3b8';
    if (score >= 70) return '#22c55e';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  };

  const formatPrice = (price: string | undefined) => {
    if (!price) return '-';
    const num = typeof price === 'string' ? parseFloat(price.replace(/[^0-9.]/g, '')) : price;
    if (isNaN(num)) return price;
    return '$' + num.toLocaleString();
  };

  const ScoreCircle: React.FC<{ score: number | undefined; label: string }> = ({ score, label }) => (
    <div className="score-item">
      <div
        className="score-circle"
        style={{ borderColor: getScoreColor(score) }}
      >
        <span style={{ color: getScoreColor(score) }}>
          {score ?? '-'}
        </span>
      </div>
      <span className="score-label">{label}</span>
    </div>
  );

  return (
    <div className="compare-page">
      <SEOHead
        title="Compare Properties - Perchspot"
        description="Compare multiple properties side-by-side with AI-powered analysis. Evaluate condition, schools, investment potential, and location quality."
        path="/compare"
      />
      <div className="compare-header">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
          <h1>Compare Properties</h1>
        </div>
        <div className="header-actions">
          <Link to="/account?tab=favorites" className="nav-link">
            Favorites
          </Link>
          <Link to="/account?tab=history" className="nav-link">
            History
          </Link>
          <Link to="/" className="btn-secondary">
            New Analysis
          </Link>
        </div>
      </div>

      <div className="compare-content">
        <div className="input-section">
          <h2>Enter properties to compare</h2>
          <p className="subtitle">Add 2-3 property addresses for side-by-side comparison</p>

          <div className="address-inputs">
            {addresses.map((address, index) => (
              <div key={index} className="address-row">
                <span className="address-number">{index + 1}</span>
                <input
                  type="text"
                  placeholder="Enter property address..."
                  value={address}
                  onChange={(e) => handleAddressChange(index, e.target.value)}
                  className="address-input"
                />
                {addresses.length > 2 && (
                  <button
                    className="remove-input-btn"
                    onClick={() => removeAddress(index)}
                    title="Remove"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="18" y1="6" x2="6" y2="18" />
                      <line x1="6" y1="6" x2="18" y2="18" />
                    </svg>
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="input-actions">
            {addresses.length < 3 && (
              <button className="add-btn" onClick={addAddress}>
                + Add another property
              </button>
            )}
            <button
              className="compare-btn"
              onClick={handleCompare}
              disabled={loading || addresses.filter((a) => a.trim()).length < 2}
            >
              {loading ? 'Comparing...' : 'Compare Properties'}
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}
        </div>

        {loading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Analyzing properties... This may take a moment.</p>
          </div>
        )}

        {result && !loading && (
          <div className="results-section">
            {result.comparison_notes && (
              <div className="comparison-notes">
                <strong>Summary:</strong> {result.comparison_notes}
              </div>
            )}

            <div className="properties-grid">
              {result.properties.map((property, index) => (
                <PropertyCard key={index} property={property} rank={index + 1} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const PropertyCard: React.FC<{ property: PropertySummary; rank: number }> = ({
  property,
  rank,
}) => {
  const getScoreColor = (score: number | undefined) => {
    if (score === undefined) return '#94a3b8';
    if (score >= 70) return '#22c55e';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  };

  const formatPrice = (price: string | undefined) => {
    if (!price) return '-';
    const num = typeof price === 'string' ? parseFloat(price.replace(/[^0-9.]/g, '')) : price;
    if (isNaN(num)) return String(price);
    return '$' + num.toLocaleString();
  };

  return (
    <div className="property-card">
      <div className="card-header">
        <span className="rank">#{rank}</span>
        {property.cached && <span className="cached-badge">Cached</span>}
      </div>

      <h3 className="address">{property.address}</h3>

      <div className="property-stats">
        <span className="stat">{formatPrice(property.price)}</span>
        {property.beds && <span className="stat">{property.beds} bd</span>}
        {property.baths && <span className="stat">{property.baths} ba</span>}
        {property.sqft && <span className="stat">{property.sqft.toLocaleString()} sqft</span>}
      </div>

      <div className="scores-section">
        <div className="overall-score" style={{ borderColor: getScoreColor(property.scores.overall) }}>
          <span className="score-value" style={{ color: getScoreColor(property.scores.overall) }}>
            {property.scores.overall ?? '-'}
          </span>
          <span className="score-title">Overall</span>
        </div>

        <div className="sub-scores">
          <div className="sub-score">
            <span className="label">Property</span>
            <span className="value" style={{ color: getScoreColor(property.scores.property) }}>
              {property.scores.property ?? '-'}
            </span>
          </div>
          <div className="sub-score">
            <span className="label">Location</span>
            <span className="value" style={{ color: getScoreColor(property.scores.location) }}>
              {property.scores.location ?? '-'}
            </span>
          </div>
          <div className="sub-score">
            <span className="label">Schools</span>
            <span className="value" style={{ color: getScoreColor(property.scores.schools) }}>
              {property.scores.schools ?? '-'}
            </span>
          </div>
          <div className="sub-score">
            <span className="label">Investment</span>
            <span className="value" style={{ color: getScoreColor(property.scores.investment) }}>
              {property.scores.investment ?? '-'}
            </span>
          </div>
        </div>
      </div>

      {property.strengths.length > 0 && (
        <div className="pros-cons">
          <h4>Strengths</h4>
          <ul className="strengths-list">
            {property.strengths.slice(0, 3).map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {property.concerns.length > 0 && (
        <div className="pros-cons">
          <h4>Concerns</h4>
          <ul className="concerns-list">
            {property.concerns.slice(0, 3).map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <Link to={`/chat?address=${encodeURIComponent(property.address)}`} className="view-full-btn">
        View Full Analysis
      </Link>
    </div>
  );
};

export default ComparePage;
