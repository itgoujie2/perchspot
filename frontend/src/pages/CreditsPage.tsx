import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { promotionsApi, referralsApi } from '../services/api';

const PRESETS = [5, 10, 20];

const CreditsPage: React.FC = () => {
  const { user, updateBalance } = useAuth();
  const [amount, setAmount] = useState<number | ''>('');
  const [buying, setBuying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Promotions state
  const [surveyCompleted, setSurveyCompleted] = useState(false);
  const [claimingSurvey, setClaimingSurvey] = useState(false);
  const [showSurveyForm, setShowSurveyForm] = useState(false);
  const [surveyAnswers, setSurveyAnswers] = useState({
    howDidYouHear: '',
    satisfaction: '',
    improvements: '',
  });
  const [referralCode, setReferralCode] = useState<string | null>(null);
  const [referralLink, setReferralLink] = useState<string | null>(null);
  const [referralStats, setReferralStats] = useState<{
    pending_rewards: number;
    completed_referrals: number;
    total_earned: number;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  // Load promotions data
  useEffect(() => {
    const loadPromotions = async () => {
      try {
        const [promoStatus, refCode, refStats] = await Promise.all([
          promotionsApi.getStatus(),
          referralsApi.getMyCode(),
          referralsApi.getStats(),
        ]);
        setSurveyCompleted(promoStatus.survey_completed);
        setReferralCode(refCode.referral_code);
        setReferralLink(refCode.referral_link);
        setReferralStats(refStats);
      } catch (err) {
        console.error('Failed to load promotions:', err);
      }
    };
    if (user) {
      loadPromotions();
    }
  }, [user]);

  const handleSubmitSurvey = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate at least one field is filled
    if (!surveyAnswers.howDidYouHear && !surveyAnswers.satisfaction && !surveyAnswers.improvements) {
      setError('Please answer at least one question');
      return;
    }

    setClaimingSurvey(true);
    setError(null);
    try {
      const result = await promotionsApi.completeSurvey();
      setSurveyCompleted(true);
      setShowSurveyForm(false);
      setSuccess(result.message);
      // Update balance in context
      if (user) {
        updateBalance(user.credit_balance + result.credits_awarded);
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Failed to claim survey reward');
    } finally {
      setClaimingSurvey(false);
    }
  };

  const copyReferralLink = () => {
    if (referralLink) {
      navigator.clipboard.writeText(referralLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleBuy = async (purchaseAmount: number) => {
    if (purchaseAmount < 1 || purchaseAmount > 100) {
      setError('Amount must be between $1 and $100');
      return;
    }

    setBuying(true);
    setError(null);

    const token = localStorage.getItem('auth_token');
    if (!token) {
      setError('Please log in first');
      setBuying(false);
      return;
    }

    try {
      const res = await fetch(`${apiUrl}/api/v1/payments/create-checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ amount: purchaseAmount }),
      });

      if (!res.ok) {
        const data = await res.json();
        const msg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        throw new Error(msg || 'Failed to create checkout');
      }

      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } catch (err: any) {
      setError(err.message || 'Something went wrong');
      setBuying(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f0c29 0%, #1a1a3e 50%, #24243e 100%)',
      color: 'white',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
      padding: '2rem',
    }}>
      <div style={{ maxWidth: 500, margin: '0 auto' }}>
        <div style={{ marginBottom: '2rem' }}>
          <Link to="/" style={{ color: 'rgba(255,255,255,0.6)', textDecoration: 'none', fontSize: '0.9rem' }}>
            &larr; Back to Home
          </Link>
        </div>

        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Buy Credits</h1>
        <p style={{ color: 'rgba(255,255,255,0.5)', marginBottom: '2rem' }}>
          1 credit = $1. Credits are used for Perchspot property analyses and follow-up questions.
        </p>

        {user && (
          <div style={{
            background: 'rgba(255,255,255,0.08)',
            borderRadius: 12,
            padding: '1rem 1.5rem',
            marginBottom: '2rem',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
          }}>
            <span style={{ opacity: 0.7 }}>Current Balance:</span>
            <span style={{ fontSize: '1.4rem', fontWeight: 700 }}>
              ${user.credit_balance.toFixed(2)}
            </span>
          </div>
        )}

        {error && (
          <div style={{
            background: 'rgba(244,67,54,0.15)',
            border: '1px solid rgba(244,67,54,0.3)',
            borderRadius: 8,
            padding: '0.75rem 1rem',
            marginBottom: '1.5rem',
            color: '#ff6b6b',
          }}>
            {error}
          </div>
        )}

        {success && (
          <div style={{
            background: 'rgba(76,175,80,0.15)',
            border: '1px solid rgba(76,175,80,0.3)',
            borderRadius: 8,
            padding: '0.75rem 1rem',
            marginBottom: '1.5rem',
            color: '#81c784',
          }}>
            {success}
          </div>
        )}

        {/* Preset amounts */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {PRESETS.map(preset => (
            <button
              key={preset}
              onClick={() => handleBuy(preset)}
              disabled={buying}
              style={{
                flex: 1,
                padding: '1.25rem 0',
                borderRadius: 12,
                border: '1px solid rgba(255,255,255,0.15)',
                background: 'rgba(255,255,255,0.06)',
                color: 'white',
                cursor: buying ? 'wait' : 'pointer',
                opacity: buying ? 0.5 : 1,
              }}
            >
              <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>${preset}</div>
              <div style={{ fontSize: '0.8rem', opacity: 0.5, marginTop: '0.25rem' }}>{preset} credits</div>
            </button>
          ))}
        </div>

        {/* Custom amount */}
        <div style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 12,
          padding: '1.25rem',
        }}>
          <div style={{ fontSize: '0.85rem', opacity: 0.6, marginBottom: '0.75rem' }}>Or enter a custom amount ($1–$100)</div>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <span style={{
                position: 'absolute',
                left: 12,
                top: '50%',
                transform: 'translateY(-50%)',
                opacity: 0.5,
                fontSize: '1rem',
              }}>$</span>
              <input
                type="number"
                min={1}
                max={100}
                value={amount}
                onChange={e => setAmount(e.target.value === '' ? '' : parseInt(e.target.value))}
                placeholder="Amount"
                style={{
                  width: '100%',
                  padding: '0.7rem 0.75rem 0.7rem 1.5rem',
                  borderRadius: 8,
                  border: '1px solid rgba(255,255,255,0.2)',
                  background: 'rgba(255,255,255,0.08)',
                  color: 'white',
                  fontSize: '1rem',
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <button
              onClick={() => amount && handleBuy(amount)}
              disabled={buying || !amount}
              style={{
                padding: '0.7rem 1.5rem',
                borderRadius: 8,
                border: 'none',
                background: amount ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'rgba(255,255,255,0.1)',
                color: 'white',
                fontSize: '1rem',
                fontWeight: 600,
                cursor: buying || !amount ? 'default' : 'pointer',
                opacity: buying || !amount ? 0.5 : 1,
              }}
            >
              {buying ? '...' : 'Buy'}
            </button>
          </div>
        </div>

        {/* First Purchase Bonus Notice */}
        <div style={{
          background: 'rgba(102, 126, 234, 0.1)',
          border: '1px solid rgba(102, 126, 234, 0.2)',
          borderRadius: 12,
          padding: '1rem 1.25rem',
          marginTop: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
        }}>
          <span style={{ fontSize: '1.5rem' }}>🎁</span>
          <div>
            <div style={{ fontWeight: 600, color: '#a8b4ff' }}>First Purchase Bonus</div>
            <div style={{ fontSize: '0.85rem', opacity: 0.7 }}>Get 10% extra credits on your first purchase!</div>
          </div>
        </div>

        {/* Free Credits Section */}
        <h2 style={{ fontSize: '1.5rem', marginTop: '3rem', marginBottom: '1rem' }}>Earn Free Credits</h2>
        <p style={{ color: 'rgba(255,255,255,0.5)', marginBottom: '1.5rem' }}>
          Complete these actions to earn bonus credits.
        </p>

        {/* Feedback Survey */}
        <div style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 12,
          padding: '1.25rem',
          marginBottom: '1rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Give Feedback</div>
              <div style={{ fontSize: '0.85rem', opacity: 0.6 }}>Complete a quick survey and earn $1.00</div>
            </div>
            <div style={{
              background: surveyCompleted ? 'rgba(76,175,80,0.2)' : 'rgba(255,193,7,0.2)',
              color: surveyCompleted ? '#81c784' : '#ffd54f',
              padding: '0.25rem 0.75rem',
              borderRadius: 20,
              fontSize: '0.75rem',
              fontWeight: 600,
            }}>
              {surveyCompleted ? 'Claimed' : '$1.00'}
            </div>
          </div>

          {!surveyCompleted && !showSurveyForm && (
            <button
              onClick={() => setShowSurveyForm(true)}
              style={{
                width: '100%',
                padding: '0.6rem 1rem',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'transparent',
                color: 'white',
                fontSize: '0.9rem',
                cursor: 'pointer',
              }}
            >
              Take Survey
            </button>
          )}

          {!surveyCompleted && showSurveyForm && (
            <form onSubmit={handleSubmitSurvey}>
              {/* Question 1 */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', opacity: 0.8 }}>
                  How did you hear about Perchspot?
                </label>
                <select
                  value={surveyAnswers.howDidYouHear}
                  onChange={e => setSurveyAnswers(prev => ({ ...prev, howDidYouHear: e.target.value }))}
                  style={{
                    width: '100%',
                    padding: '0.6rem',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.2)',
                    background: 'rgba(255,255,255,0.08)',
                    color: 'white',
                    fontSize: '0.9rem',
                  }}
                >
                  <option value="" style={{ background: '#1a1a3e' }}>Select an option...</option>
                  <option value="search" style={{ background: '#1a1a3e' }}>Search engine (Google, etc.)</option>
                  <option value="social" style={{ background: '#1a1a3e' }}>Social media</option>
                  <option value="friend" style={{ background: '#1a1a3e' }}>Friend or colleague</option>
                  <option value="realtor" style={{ background: '#1a1a3e' }}>Real estate agent</option>
                  <option value="other" style={{ background: '#1a1a3e' }}>Other</option>
                </select>
              </div>

              {/* Question 2 */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', opacity: 0.8 }}>
                  How satisfied are you with Perchspot?
                </label>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {['1', '2', '3', '4', '5'].map(num => (
                    <button
                      key={num}
                      type="button"
                      onClick={() => setSurveyAnswers(prev => ({ ...prev, satisfaction: num }))}
                      style={{
                        flex: 1,
                        padding: '0.5rem',
                        borderRadius: 8,
                        border: surveyAnswers.satisfaction === num
                          ? '2px solid #667eea'
                          : '1px solid rgba(255,255,255,0.2)',
                        background: surveyAnswers.satisfaction === num
                          ? 'rgba(102, 126, 234, 0.2)'
                          : 'rgba(255,255,255,0.08)',
                        color: 'white',
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                      }}
                    >
                      {num}
                    </button>
                  ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', opacity: 0.5, marginTop: '0.25rem' }}>
                  <span>Not satisfied</span>
                  <span>Very satisfied</span>
                </div>
              </div>

              {/* Question 3 */}
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', opacity: 0.8 }}>
                  What could we improve? (optional)
                </label>
                <textarea
                  value={surveyAnswers.improvements}
                  onChange={e => setSurveyAnswers(prev => ({ ...prev, improvements: e.target.value }))}
                  placeholder="Your feedback helps us improve..."
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '0.6rem',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.2)',
                    background: 'rgba(255,255,255,0.08)',
                    color: 'white',
                    fontSize: '0.9rem',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Submit buttons */}
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button
                  type="button"
                  onClick={() => setShowSurveyForm(false)}
                  style={{
                    flex: 1,
                    padding: '0.6rem 1rem',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.2)',
                    background: 'transparent',
                    color: 'white',
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={claimingSurvey}
                  style={{
                    flex: 1,
                    padding: '0.6rem 1rem',
                    borderRadius: 8,
                    border: 'none',
                    background: 'linear-gradient(135deg, #667eea, #764ba2)',
                    color: 'white',
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    cursor: claimingSurvey ? 'wait' : 'pointer',
                    opacity: claimingSurvey ? 0.5 : 1,
                  }}
                >
                  {claimingSurvey ? 'Submitting...' : 'Submit & Claim $1.00'}
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Referral Program */}
        <div style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 12,
          padding: '1.25rem',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Refer Friends</div>
              <div style={{ fontSize: '0.85rem', opacity: 0.6 }}>Earn $1.00 when friends make their first purchase</div>
            </div>
            <div style={{
              background: 'rgba(102, 126, 234, 0.2)',
              color: '#a8b4ff',
              padding: '0.25rem 0.75rem',
              borderRadius: 20,
              fontSize: '0.75rem',
              fontWeight: 600,
            }}>
              $1.00 each
            </div>
          </div>

          {referralLink && (
            <div style={{
              display: 'flex',
              gap: '0.5rem',
              background: 'rgba(0,0,0,0.2)',
              borderRadius: 8,
              padding: '0.5rem',
              marginBottom: '1rem',
            }}>
              <input
                type="text"
                value={referralLink}
                readOnly
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  color: 'rgba(255,255,255,0.8)',
                  fontSize: '0.85rem',
                  padding: '0.25rem 0.5rem',
                }}
              />
              <button
                onClick={copyReferralLink}
                style={{
                  padding: '0.4rem 0.75rem',
                  borderRadius: 6,
                  border: 'none',
                  background: copied ? 'rgba(76,175,80,0.3)' : 'rgba(255,255,255,0.1)',
                  color: copied ? '#81c784' : 'white',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                }}
              >
                {copied ? 'Copied!' : 'Copy'}
              </button>
            </div>
          )}

          {referralStats && (
            <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
              <div style={{ opacity: 0.6 }}>
                Pending: <span style={{ color: '#ffd54f' }}>{referralStats.pending_rewards}</span>
              </div>
              <div style={{ opacity: 0.6 }}>
                Completed: <span style={{ color: '#81c784' }}>{referralStats.completed_referrals}</span>
              </div>
              <div style={{ opacity: 0.6 }}>
                Earned: <span style={{ color: '#a8b4ff' }}>${referralStats.total_earned.toFixed(2)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CreditsPage;
