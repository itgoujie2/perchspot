import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { trackEvent, AnalyticsEvents } from '../hooks/useAnalytics';
import './ExitIntentPopup.css';

const POPUP_STORAGE_KEY = 'perchspot_exit_popup_shown';
const POPUP_COOLDOWN_DAYS = 7;

interface ExitIntentPopupProps {
  /** Whether to enable the popup (default: true) */
  enabled?: boolean;
}

const ExitIntentPopup: React.FC<ExitIntentPopupProps> = ({ enabled = true }) => {
  const { user } = useAuth();
  const [isVisible, setIsVisible] = useState(false);
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const shouldShowPopup = useCallback(() => {
    // Don't show if user is logged in
    if (user) return false;

    // Check if we've shown it recently
    const lastShown = localStorage.getItem(POPUP_STORAGE_KEY);
    if (lastShown) {
      const daysSinceShown = (Date.now() - parseInt(lastShown)) / (1000 * 60 * 60 * 24);
      if (daysSinceShown < POPUP_COOLDOWN_DAYS) return false;
    }

    return true;
  }, [user]);

  useEffect(() => {
    if (!enabled || !shouldShowPopup()) return;

    let triggered = false;

    const handleMouseLeave = (e: MouseEvent) => {
      // Only trigger when mouse leaves through the top of the viewport
      if (e.clientY <= 0 && !triggered) {
        triggered = true;
        setIsVisible(true);
        localStorage.setItem(POPUP_STORAGE_KEY, Date.now().toString());
      }
    };

    // Add a small delay before enabling exit intent detection
    const timeout = setTimeout(() => {
      document.addEventListener('mouseleave', handleMouseLeave);
    }, 5000);

    return () => {
      clearTimeout(timeout);
      document.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [enabled, shouldShowPopup]);

  const handleClose = () => {
    setIsVisible(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    try {
      // For now, we'll store this in localStorage
      // In production, this should send to a backend endpoint or email service
      const existingEmails = JSON.parse(localStorage.getItem('newsletter_subscribers') || '[]');
      if (!existingEmails.includes(email)) {
        existingEmails.push(email);
        localStorage.setItem('newsletter_subscribers', JSON.stringify(existingEmails));
      }

      setSubmitted(true);
      trackEvent('newsletter_signup', { email_domain: email.split('@')[1] });

      // Close after showing success message
      setTimeout(() => {
        setIsVisible(false);
      }, 2000);
    } catch (err) {
      setError('Something went wrong. Please try again.');
    }
  };

  if (!isVisible) return null;

  return (
    <div className="exit-popup-overlay" onClick={handleClose}>
      <div className="exit-popup" onClick={(e) => e.stopPropagation()}>
        <button className="exit-popup-close" onClick={handleClose} aria-label="Close">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="20" height="20">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {submitted ? (
          <div className="exit-popup-success">
            <div className="success-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="48" height="48">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </div>
            <h3>You're on the list!</h3>
            <p>We'll send you home buying tips and market insights.</p>
          </div>
        ) : (
          <>
            <div className="exit-popup-header">
              <div className="exit-popup-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="32" height="32">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                  <polyline points="22,6 12,13 2,6"/>
                </svg>
              </div>
              <h3>Wait! Don't miss out</h3>
              <p>Get exclusive home buying tips and market insights delivered to your inbox.</p>
            </div>

            <form className="exit-popup-form" onSubmit={handleSubmit}>
              <input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="exit-popup-input"
                autoFocus
              />
              {error && <span className="exit-popup-error">{error}</span>}
              <button type="submit" className="exit-popup-submit">
                Subscribe for Free
              </button>
            </form>

            <div className="exit-popup-benefits">
              <div className="benefit">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Weekly market insights
              </div>
              <div className="benefit">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                Home buying tips
              </div>
              <div className="benefit">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                No spam, unsubscribe anytime
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ExitIntentPopup;
