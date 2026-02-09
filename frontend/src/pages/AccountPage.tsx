import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { favoritesApi, historyApi, compareApi } from '../services/api';
import type { Favorite, HistoryItem, CompareResponse } from '../types';
import Logo from '../assets/logo.svg';
import SEOHead from '../components/SEOHead';
import './AccountPage.css';

type TabType = 'profile' | 'favorites' | 'history';

const AccountPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, logout, isLoading } = useAuth();

  const initialTab = (searchParams.get('tab') as TabType) || 'profile';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // Debug: Log auth state
  console.log('AccountPage render:', { user: user?.email, isLoading });

  // Favorites state
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareResponse | null>(null);

  // History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    const tab = searchParams.get('tab') as TabType;
    if (tab && ['profile', 'favorites', 'history'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    if (activeTab === 'favorites') {
      loadFavorites();
    } else if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    setSearchParams({ tab });
    setCompareResult(null);
  };

  const loadFavorites = async () => {
    try {
      setFavoritesLoading(true);
      const response = await favoritesApi.list();
      setFavorites(response.favorites);
    } catch (err) {
      console.error('Failed to load favorites:', err);
    } finally {
      setFavoritesLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      setHistoryLoading(true);
      const response = await historyApi.list();
      setHistory(response.items);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleRemoveFavorite = async (favoriteId: string) => {
    try {
      await favoritesApi.remove(favoriteId);
      setFavorites(favorites.filter((f) => f.id !== favoriteId));
      setSelectedForCompare(prev => {
        const next = new Set(prev);
        next.delete(favoriteId);
        return next;
      });
    } catch (err) {
      console.error('Failed to remove favorite:', err);
    }
  };

  const toggleCompareSelection = (favoriteId: string) => {
    setSelectedForCompare(prev => {
      const next = new Set(prev);
      if (next.has(favoriteId)) {
        next.delete(favoriteId);
      } else if (next.size < 3) {
        next.add(favoriteId);
      }
      return next;
    });
  };

  const handleCompare = async () => {
    const selectedAddresses = favorites
      .filter(f => selectedForCompare.has(f.id))
      .map(f => f.address);

    if (selectedAddresses.length < 2) return;

    try {
      setComparing(true);
      const result = await compareApi.compare({ addresses: selectedAddresses });
      setCompareResult(result);
    } catch (err) {
      console.error('Compare failed:', err);
    } finally {
      setComparing(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getScoreColor = (score: number | undefined) => {
    if (score === undefined) return '#94a3b8';
    if (score >= 70) return '#22c55e';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  };

  // Handle loading and missing user states
  if (isLoading || !user) {
    return (
      <div style={{
        minHeight: '100vh',
        background: '#f8fafc',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <div style={{
          width: 40,
          height: 40,
          border: '3px solid #e2e8f0',
          borderTopColor: '#667eea',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }}></div>
        <p style={{ color: '#64748b', margin: 0 }}>Loading account...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <div className="account-page">
      <SEOHead
        title="My Account - Perchspot"
        description="Manage your Perchspot account, view saved properties, and access analysis history."
        path="/account"
        noindex={true}
      />
      <header className="account-header">
        <Link to="/" className="logo-link">
          <img src={Logo} alt="Perchspot" className="header-logo" />
        </Link>
        <Link to="/" className="new-analysis-btn">New Analysis</Link>
      </header>

      <div className="account-content">
        <div className="account-sidebar">
          <div className="user-card">
            <div className="user-avatar-large">
              {user.email.charAt(0).toUpperCase()}
            </div>
            <div className="user-email-display">{user.email}</div>
            <div className="user-credits-display">${user.credit_balance.toFixed(2)} credits</div>
          </div>

          <nav className="account-nav">
            <button
              className={`nav-item ${activeTab === 'profile' ? 'active' : ''}`}
              onClick={() => handleTabChange('profile')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              Profile
            </button>
            <button
              className={`nav-item ${activeTab === 'favorites' ? 'active' : ''}`}
              onClick={() => handleTabChange('favorites')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
              Favorites
              {favorites.length > 0 && <span className="badge">{favorites.length}</span>}
            </button>
            <button
              className={`nav-item ${activeTab === 'history' ? 'active' : ''}`}
              onClick={() => handleTabChange('history')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
              History
            </button>
          </nav>
        </div>

        <main className="account-main">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="tab-content profile-tab">
              <h2>Profile</h2>
              <div className="profile-section">
                <h3>Account Information</h3>
                <div className="info-row">
                  <span className="info-label">Email</span>
                  <span className="info-value">{user.email}</span>
                </div>
                <div className="info-row">
                  <span className="info-label">Credit Balance</span>
                  <span className="info-value">${user.credit_balance.toFixed(2)}</span>
                </div>
              </div>
              <div className="profile-actions">
                <Link to="/credits" className="btn-primary">Buy Credits</Link>
                <button onClick={logout} className="btn-danger">Sign Out</button>
              </div>
            </div>
          )}

          {/* Favorites Tab */}
          {activeTab === 'favorites' && (
            <div className="tab-content favorites-tab">
              <div className="tab-header">
                <h2>Saved Properties</h2>
                {selectedForCompare.size >= 2 && (
                  <button
                    className="compare-btn"
                    onClick={handleCompare}
                    disabled={comparing}
                  >
                    {comparing ? 'Comparing...' : `Compare ${selectedForCompare.size} Properties`}
                  </button>
                )}
              </div>

              {selectedForCompare.size > 0 && selectedForCompare.size < 2 && (
                <div className="compare-hint">
                  Select {2 - selectedForCompare.size} more to compare
                </div>
              )}

              {/* Compare Results */}
              {compareResult && (
                <div className="compare-results">
                  <div className="compare-results-header">
                    <h3>Comparison Results</h3>
                    <button onClick={() => setCompareResult(null)} className="close-compare">
                      Close
                    </button>
                  </div>
                  {compareResult.comparison_notes && (
                    <div className="comparison-summary">{compareResult.comparison_notes}</div>
                  )}
                  <div className="compare-grid">
                    {compareResult.properties.map((prop, idx) => (
                      <div key={idx} className="compare-card">
                        <div className="compare-rank">#{idx + 1}</div>
                        <h4>{prop.address}</h4>
                        <div className="compare-stats">
                          {prop.price && <span>{prop.price}</span>}
                          {prop.beds && <span>{prop.beds} bd</span>}
                          {prop.baths && <span>{prop.baths} ba</span>}
                        </div>
                        <div
                          className="compare-score"
                          style={{ borderColor: getScoreColor(prop.scores.overall) }}
                        >
                          <span style={{ color: getScoreColor(prop.scores.overall) }}>
                            {prop.scores.overall ?? '—'}
                          </span>
                          <small>Overall</small>
                        </div>
                        {prop.needs_analysis && (
                          <div className="needs-analysis-badge">Needs Analysis</div>
                        )}
                        <Link
                          to={`/chat?address=${encodeURIComponent(prop.address)}`}
                          className="view-link"
                        >
                          View Full Analysis
                        </Link>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {favoritesLoading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading favorites...</p>
                </div>
              ) : favorites.length === 0 ? (
                <div className="empty-state">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                  <h3>No favorites yet</h3>
                  <p>Save properties by clicking the heart icon during analysis</p>
                  <Link to="/" className="btn-primary">Analyze a Property</Link>
                </div>
              ) : (
                <div className="favorites-list">
                  {favorites.map((fav) => (
                    <div
                      key={fav.id}
                      className={`favorite-item ${selectedForCompare.has(fav.id) ? 'selected' : ''}`}
                    >
                      <label className="compare-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedForCompare.has(fav.id)}
                          onChange={() => toggleCompareSelection(fav.id)}
                          disabled={!selectedForCompare.has(fav.id) && selectedForCompare.size >= 3}
                        />
                        <span className="checkmark"></span>
                      </label>
                      <div className="favorite-content">
                        <h4>{fav.address}</h4>
                        {fav.nickname && <span className="nickname">{fav.nickname}</span>}
                        <span className="date">Saved {formatDate(fav.created_at)}</span>
                      </div>
                      <div className="favorite-actions">
                        <Link
                          to={`/chat?address=${encodeURIComponent(fav.address)}`}
                          className="action-btn view"
                        >
                          View
                        </Link>
                        <button
                          onClick={() => handleRemoveFavorite(fav.id)}
                          className="action-btn remove"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* History Tab */}
          {activeTab === 'history' && (
            <div className="tab-content history-tab">
              <h2>Analysis History</h2>

              {historyLoading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading history...</p>
                </div>
              ) : history.length === 0 ? (
                <div className="empty-state">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="12" cy="12" r="10" />
                    <polyline points="12,6 12,12 16,14" />
                  </svg>
                  <h3>No analyses yet</h3>
                  <p>Your property analysis history will appear here</p>
                  <Link to="/" className="btn-primary">Analyze a Property</Link>
                </div>
              ) : (
                <div className="history-list">
                  {history.map((item) => (
                    <div key={item.id} className="history-item">
                      <div className="history-content">
                        <h4>{item.address}</h4>
                        <span className="date">{formatDate(item.analyzed_at)}</span>
                      </div>
                      <div className="history-meta">
                        <span className="cost">${item.cost.toFixed(2)}</span>
                        <Link
                          to={`/chat?address=${encodeURIComponent(item.address)}`}
                          className="action-btn view"
                        >
                          View
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default AccountPage;
