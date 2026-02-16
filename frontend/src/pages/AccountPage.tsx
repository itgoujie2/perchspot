import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { favoritesApi, historyApi, referralsApi } from '../services/api';
import type { Favorite, HistoryItem } from '../types';
import Logo from '../assets/logo.svg';
import SEOHead from '../components/SEOHead';
import './AccountPage.css';

type TabType = 'profile' | 'favorites' | 'history' | 'referrals';

interface ReferralData {
  referral_code: string;
  referral_link: string;
}

interface ReferralStats {
  pending_rewards: number;
  completed_referrals: number;
  total_earned: number;
}

const AccountPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, logout, isLoading } = useAuth();

  const initialTab = (searchParams.get('tab') as TabType) || 'profile';
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);

  // Debug: Log auth state
  console.log('AccountPage render:', { user: user?.email, isLoading });

  // Favorites state
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [favoritesLoading, setFavoritesLoading] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<Set<string>>(new Set());

  // History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedHistoryForCompare, setSelectedHistoryForCompare] = useState<Set<string>>(new Set());

  // Referral state
  const [referralData, setReferralData] = useState<ReferralData | null>(null);
  const [referralStats, setReferralStats] = useState<ReferralStats | null>(null);
  const [referralLoading, setReferralLoading] = useState(false);
  const [referralCopied, setReferralCopied] = useState(false);

  useEffect(() => {
    const tab = searchParams.get('tab') as TabType;
    if (tab && ['profile', 'favorites', 'history', 'referrals'].includes(tab)) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  useEffect(() => {
    if (activeTab === 'favorites') {
      loadFavorites();
    } else if (activeTab === 'history') {
      loadHistory();
    } else if (activeTab === 'referrals') {
      loadReferrals();
    }
  }, [activeTab]);

  const loadReferrals = async () => {
    try {
      setReferralLoading(true);
      const [codeResponse, statsResponse] = await Promise.all([
        referralsApi.getMyCode(),
        referralsApi.getStats(),
      ]);
      setReferralData(codeResponse);
      setReferralStats(statsResponse);
    } catch (err) {
      console.error('Failed to load referral data:', err);
    } finally {
      setReferralLoading(false);
    }
  };

  const handleCopyReferralLink = async () => {
    if (!referralData) return;
    try {
      await navigator.clipboard.writeText(referralData.referral_link);
      setReferralCopied(true);
      setTimeout(() => setReferralCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleReferralShare = (platform: 'twitter' | 'facebook' | 'email') => {
    if (!referralData) return;
    const shareText = 'I just discovered an amazing AI property analysis tool! Get $1 credit when you sign up with my link:';

    switch (platform) {
      case 'twitter':
        window.open(
          `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(referralData.referral_link)}`,
          '_blank',
          'width=550,height=420'
        );
        break;
      case 'facebook':
        window.open(
          `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(referralData.referral_link)}`,
          '_blank',
          'width=550,height=420'
        );
        break;
      case 'email':
        const subject = 'Check out Perchspot - AI Property Analysis';
        const body = `${shareText}\n\n${referralData.referral_link}`;
        window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
        break;
    }
  };

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    setSearchParams({ tab });
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
      } else if (next.size < 2) {
        next.add(favoriteId);
      }
      return next;
    });
  };

  const toggleHistorySelection = (itemId: string) => {
    setSelectedHistoryForCompare(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else if (next.size < 2) {
        next.add(itemId);
      }
      return next;
    });
  };

  const handleCompareFromFavorites = () => {
    const selectedAddresses = favorites
      .filter(f => selectedForCompare.has(f.id))
      .map(f => encodeURIComponent(f.address));
    navigate(`/compare?addresses=${selectedAddresses.join(',')}`);
  };

  const handleCompareFromHistory = () => {
    const selectedAddresses = history
      .filter(item => selectedHistoryForCompare.has(item.id))
      .map(item => encodeURIComponent(item.address));
    navigate(`/compare?addresses=${selectedAddresses.join(',')}`);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
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
            <button
              className={`nav-item ${activeTab === 'referrals' ? 'active' : ''}`}
              onClick={() => handleTabChange('referrals')}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
              Referrals
              {referralStats && referralStats.total_earned > 0 && (
                <span className="badge earned">${referralStats.total_earned.toFixed(0)}</span>
              )}
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
                    onClick={handleCompareFromFavorites}
                  >
                    Compare {selectedForCompare.size} Properties
                  </button>
                )}
              </div>

              {selectedForCompare.size > 0 && selectedForCompare.size < 2 && (
                <div className="compare-hint">
                  Select {2 - selectedForCompare.size} more to compare
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
                          disabled={!selectedForCompare.has(fav.id) && selectedForCompare.size >= 2}
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
              <div className="tab-header">
                <h2>Analysis History</h2>
                {selectedHistoryForCompare.size >= 2 && (
                  <button
                    className="compare-btn"
                    onClick={handleCompareFromHistory}
                  >
                    Compare {selectedHistoryForCompare.size} Properties
                  </button>
                )}
              </div>

              {selectedHistoryForCompare.size > 0 && selectedHistoryForCompare.size < 2 && (
                <div className="compare-hint">
                  Select {2 - selectedHistoryForCompare.size} more to compare
                </div>
              )}

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
                    <div
                      key={item.id}
                      className={`history-item ${selectedHistoryForCompare.has(item.id) ? 'selected' : ''}`}
                    >
                      <label className="compare-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedHistoryForCompare.has(item.id)}
                          onChange={() => toggleHistorySelection(item.id)}
                          disabled={!selectedHistoryForCompare.has(item.id) && selectedHistoryForCompare.size >= 2}
                        />
                        <span className="checkmark"></span>
                      </label>
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

          {/* Referrals Tab */}
          {activeTab === 'referrals' && (
            <div className="tab-content referrals-tab">
              <h2>Refer Friends, Earn Credits</h2>

              {referralLoading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Loading referral data...</p>
                </div>
              ) : (
                <>
                  <div className="referral-hero">
                    <div className="referral-hero-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="32" height="32">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                      </svg>
                    </div>
                    <h3>Get $1 for every friend who signs up</h3>
                    <p>Share your unique referral link and earn credits when your friends create an account.</p>
                  </div>

                  {referralStats && (
                    <div className="referral-stats-grid">
                      <div className="stat-card">
                        <span className="stat-number">{referralStats.completed_referrals}</span>
                        <span className="stat-label">Successful Referrals</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-number">${referralStats.total_earned.toFixed(2)}</span>
                        <span className="stat-label">Total Earned</span>
                      </div>
                      <div className="stat-card">
                        <span className="stat-number">{referralStats.pending_rewards}</span>
                        <span className="stat-label">Pending</span>
                      </div>
                    </div>
                  )}

                  {referralData && (
                    <div className="referral-link-section">
                      <h4>Your Referral Link</h4>
                      <div className="referral-link-container">
                        <input
                          type="text"
                          value={referralData.referral_link}
                          readOnly
                          className="referral-link-input"
                        />
                        <button
                          className={`copy-btn ${referralCopied ? 'copied' : ''}`}
                          onClick={handleCopyReferralLink}
                        >
                          {referralCopied ? 'Copied!' : 'Copy Link'}
                        </button>
                      </div>

                      <div className="referral-share-section">
                        <span className="share-label">Share via:</span>
                        <div className="share-buttons">
                          <button
                            className="share-btn twitter"
                            onClick={() => handleReferralShare('twitter')}
                          >
                            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                              <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                            </svg>
                            Twitter
                          </button>
                          <button
                            className="share-btn facebook"
                            onClick={() => handleReferralShare('facebook')}
                          >
                            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                              <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                            </svg>
                            Facebook
                          </button>
                          <button
                            className="share-btn email"
                            onClick={() => handleReferralShare('email')}
                          >
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                              <polyline points="22,6 12,13 2,6"/>
                            </svg>
                            Email
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="referral-how-it-works">
                    <h4>How it works</h4>
                    <div className="steps">
                      <div className="step">
                        <div className="step-number">1</div>
                        <div className="step-content">
                          <h5>Share your link</h5>
                          <p>Send your unique referral link to friends</p>
                        </div>
                      </div>
                      <div className="step">
                        <div className="step-number">2</div>
                        <div className="step-content">
                          <h5>Friends sign up</h5>
                          <p>They create an account using your link</p>
                        </div>
                      </div>
                      <div className="step">
                        <div className="step-number">3</div>
                        <div className="step-content">
                          <h5>You earn $1</h5>
                          <p>Get $1 credit added to your account</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default AccountPage;
