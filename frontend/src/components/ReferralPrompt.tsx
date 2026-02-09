import React, { useState, useEffect } from 'react';
import { referralsApi } from '../services/api';
import './ReferralPrompt.css';

interface ReferralData {
  referral_code: string;
  referral_link: string;
}

interface ReferralStats {
  pending_rewards: number;
  completed_referrals: number;
  total_earned: number;
}

const ReferralPrompt: React.FC = () => {
  const [referralData, setReferralData] = useState<ReferralData | null>(null);
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const loadReferralData = async () => {
      try {
        const [codeResponse, statsResponse] = await Promise.all([
          referralsApi.getMyCode(),
          referralsApi.getStats(),
        ]);
        setReferralData(codeResponse);
        setStats(statsResponse);
      } catch (err) {
        console.error('Failed to load referral data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadReferralData();
  }, []);

  const handleCopyLink = async () => {
    if (!referralData) return;
    try {
      await navigator.clipboard.writeText(referralData.referral_link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleShare = (platform: 'twitter' | 'facebook' | 'email') => {
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

  if (loading || !referralData || dismissed) return null;

  return (
    <div className="referral-prompt">
      <button className="referral-dismiss" onClick={() => setDismissed(true)} aria-label="Dismiss">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      <div className="referral-header">
        <div className="referral-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="24" height="24">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
        </div>
        <div className="referral-title">
          <h4>Share with Friends, Earn $1</h4>
          <p>Get $1 credit for every friend who signs up</p>
        </div>
      </div>

      {stats && stats.total_earned > 0 && (
        <div className="referral-stats">
          <div className="stat">
            <span className="stat-value">{stats.completed_referrals}</span>
            <span className="stat-label">Referrals</span>
          </div>
          <div className="stat">
            <span className="stat-value">${stats.total_earned.toFixed(2)}</span>
            <span className="stat-label">Earned</span>
          </div>
        </div>
      )}

      <div className="referral-link-box">
        <input
          type="text"
          value={referralData.referral_link}
          readOnly
          className="referral-link-input"
        />
        <button
          className={`referral-copy-btn ${copied ? 'copied' : ''}`}
          onClick={handleCopyLink}
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>

      <div className="referral-share-buttons">
        <button
          className="referral-share-btn twitter"
          onClick={() => handleShare('twitter')}
          aria-label="Share on Twitter"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
          </svg>
          Twitter
        </button>
        <button
          className="referral-share-btn facebook"
          onClick={() => handleShare('facebook')}
          aria-label="Share on Facebook"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
          </svg>
          Facebook
        </button>
        <button
          className="referral-share-btn email"
          onClick={() => handleShare('email')}
          aria-label="Share via Email"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
          Email
        </button>
      </div>
    </div>
  );
};

export default ReferralPrompt;
