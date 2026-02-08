import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { favoritesApi } from '../services/api';
import type { Favorite } from '../types';
import Logo from '../assets/logo.svg';
import './FavoritesPage.css';

const FavoritesPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadFavorites();
  }, []);

  const loadFavorites = async () => {
    try {
      setLoading(true);
      const response = await favoritesApi.list();
      setFavorites(response.favorites);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load favorites');
    } finally {
      setLoading(false);
    }
  };

  const handleRemove = async (favoriteId: string) => {
    try {
      await favoritesApi.remove(favoriteId);
      setFavorites(favorites.filter((f) => f.id !== favoriteId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to remove favorite');
    }
  };

  const handleAnalyze = (address: string) => {
    navigate(`/chat?address=${encodeURIComponent(address)}`);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (!user) {
    return (
      <div className="favorites-page">
        <div className="favorites-header">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
        </div>
        <div className="favorites-content">
          <div className="auth-required">
            <h2>Sign in to view your favorites</h2>
            <p>Save properties you're interested in and access them anytime.</p>
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
    <div className="favorites-page">
      <div className="favorites-header">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
          <h1>My Favorites</h1>
        </div>
        <div className="header-actions">
          <Link to="/history" className="nav-link">
            History
          </Link>
          <Link to="/compare" className="nav-link">
            Compare
          </Link>
          <Link to="/" className="btn-secondary">
            New Analysis
          </Link>
        </div>
      </div>

      <div className="favorites-content">
        {loading ? (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading favorites...</p>
          </div>
        ) : error ? (
          <div className="error-state">
            <p>{error}</p>
            <button onClick={loadFavorites} className="btn-secondary">
              Try Again
            </button>
          </div>
        ) : favorites.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
            </div>
            <h2>No favorites yet</h2>
            <p>Save properties during analysis by clicking the heart icon.</p>
            <Link to="/" className="btn-primary">
              Analyze a Property
            </Link>
          </div>
        ) : (
          <div className="favorites-grid">
            {favorites.map((favorite) => (
              <div key={favorite.id} className="favorite-card">
                <div className="card-header">
                  <h3 className="address">{favorite.address}</h3>
                  <button
                    className="remove-btn"
                    onClick={() => handleRemove(favorite.id)}
                    title="Remove from favorites"
                  >
                    <svg viewBox="0 0 24 24" fill="currentColor">
                      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                    </svg>
                  </button>
                </div>
                {favorite.nickname && (
                  <p className="nickname">{favorite.nickname}</p>
                )}
                {favorite.notes && <p className="notes">{favorite.notes}</p>}
                <div className="card-footer">
                  <span className="date">Saved {formatDate(favorite.created_at)}</span>
                  <button
                    className="analyze-btn"
                    onClick={() => handleAnalyze(favorite.address)}
                  >
                    View Analysis
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default FavoritesPage;
