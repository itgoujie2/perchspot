import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { historyApi } from '../services/api';
import type { HistoryItem } from '../types';
import Logo from '../assets/logo.svg';
import './HistoryPage.css';

const HistoryPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      setLoading(true);
      const response = await historyApi.list();
      setHistory(response.items);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load history');
    } finally {
      setLoading(false);
    }
  };

  const handleViewAnalysis = (address: string) => {
    navigate(`/chat?address=${encodeURIComponent(address)}`);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(2)}`;
  };

  if (!user) {
    return (
      <div className="history-page">
        <div className="history-header">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
        </div>
        <div className="history-content">
          <div className="auth-required">
            <h2>Sign in to view your history</h2>
            <p>Your past property analyses will appear here.</p>
            <div className="auth-actions">
              <Link to="/login" className="btn-primary">
                Sign In
              </Link>
              <Link to="/register" className="btn-secondary">
                Create Account
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="history-page">
      <div className="history-header">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
          <h1>Analysis History</h1>
        </div>
        <div className="header-actions">
          <Link to="/favorites" className="nav-link">
            Favorites
          </Link>
          <Link to="/compare" className="nav-link">
            Compare
          </Link>
          <Link to="/" className="btn-secondary">
            New Analysis
          </Link>
        </div>
      </div>

      <div className="history-content">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading history...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>{error}</p>
            <button onClick={loadHistory} className="btn-secondary">
              Try Again
            </button>
          </div>
        ) : history.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
            </div>
            <h2>No analyses yet</h2>
            <p>Your property analysis history will appear here.</p>
            <Link to="/" className="btn-primary">
              Analyze a Property
            </Link>
          </div>
        ) : (
          <div className="history-list">
            <div className="list-header">
              <span className="col-address">Property Address</span>
              <span className="col-date">Date</span>
              <span className="col-cost">Cost</span>
              <span className="col-action"></span>
            </div>
            {history.map((item) => (
              <div key={item.id} className="history-item">
                <span className="col-address">{item.address}</span>
                <span className="col-date">{formatDate(item.analyzed_at)}</span>
                <span className="col-cost">{formatCost(item.cost)}</span>
                <span className="col-action">
                  <button
                    className="view-btn"
                    onClick={() => handleViewAnalysis(item.address)}
                  >
                    View
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPage;
