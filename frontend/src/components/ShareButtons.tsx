import React, { useState, RefObject } from 'react';
import html2canvas from 'html2canvas';
import './ShareButtons.css';

interface ShareButtonsProps {
  address: string;
  score?: number | null;
  price?: string | number | null;
  beds?: number | null;
  baths?: number | null;
  sqft?: number | null;
  grade?: string | null;
  reportRef?: RefObject<HTMLDivElement>;
}

const ShareButtons: React.FC<ShareButtonsProps> = ({
  address,
  score,
  price,
  beds,
  baths,
  sqft,
  grade,
  reportRef
}) => {
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [showImageModal, setShowImageModal] = useState(false);

  const shareUrl = `${window.location.origin}/chat?address=${encodeURIComponent(address)}`;

  // Build property details string
  const details: string[] = [];
  if (price) {
    const priceStr = typeof price === 'number'
      ? `$${price.toLocaleString()}`
      : price;
    details.push(priceStr);
  }
  if (beds) details.push(`${beds} bed`);
  if (baths) details.push(`${baths} bath`);
  if (sqft) details.push(`${sqft.toLocaleString()} sqft`);

  const propertyDetails = details.length > 0 ? details.join(' | ') : '';

  // Build share text with more info
  let shareText = '';
  if (score && grade) {
    shareText = `🏠 ${address}\n${propertyDetails}\n\n📊 Perchspot AI Score: ${score}/100 (Grade: ${grade})\n\nCheck out the full analysis:`;
  } else if (score) {
    shareText = `🏠 ${address}\n${propertyDetails}\n\n📊 Perchspot AI Score: ${score}/100\n\nCheck out the full analysis:`;
  } else {
    shareText = `🏠 ${address}\n${propertyDetails}\n\nCheck out this property analysis on Perchspot:`
  }

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleTwitterShare = () => {
    const twitterUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(shareText)}&url=${encodeURIComponent(shareUrl)}`;
    window.open(twitterUrl, '_blank', 'width=550,height=420');
  };

  const handleFacebookShare = () => {
    const facebookUrl = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(shareUrl)}`;
    window.open(facebookUrl, '_blank', 'width=550,height=420');
  };

  const handleLinkedInShare = () => {
    const linkedInUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(shareUrl)}`;
    window.open(linkedInUrl, '_blank', 'width=550,height=420');
  };

  const handleEmailShare = () => {
    const subject = `Property Analysis: ${address}`;
    const body = `${shareText}\n\n${shareUrl}`;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  };

  const generateReportImage = async () => {
    if (!reportRef?.current) {
      console.error('Report element not found');
      return;
    }

    setGenerating(true);
    try {
      // Get the report content element (scrollable area)
      const reportContent = reportRef.current.querySelector('.report-content') as HTMLElement;
      if (!reportContent) {
        console.error('Report content element not found');
        setGenerating(false);
        return;
      }

      // Store original styles
      const originalOverflow = reportContent.style.overflow;
      const originalHeight = reportContent.style.height;
      const originalMaxHeight = reportContent.style.maxHeight;

      // Temporarily expand to full height for capture
      reportContent.style.overflow = 'visible';
      reportContent.style.height = 'auto';
      reportContent.style.maxHeight = 'none';

      // Wait for styles to apply
      await new Promise(resolve => setTimeout(resolve, 100));

      const canvas = await html2canvas(reportRef.current, {
        scale: 2, // Higher resolution
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#f8f9fb',
        logging: false,
        windowHeight: reportRef.current.scrollHeight,
        height: reportRef.current.scrollHeight,
      });

      // Restore original styles
      reportContent.style.overflow = originalOverflow;
      reportContent.style.height = originalHeight;
      reportContent.style.maxHeight = originalMaxHeight;

      const dataUrl = canvas.toDataURL('image/png');
      setImageUrl(dataUrl);
      setShowImageModal(true);
    } catch (err) {
      console.error('Failed to generate image:', err);
      alert('Failed to generate report image. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadImage = () => {
    if (!imageUrl) return;

    const link = document.createElement('a');
    link.download = `perchspot-report-${address.replace(/[^a-zA-Z0-9]/g, '-').toLowerCase()}.png`;
    link.href = imageUrl;
    link.click();
  };

  const handleCopyImage = async () => {
    if (!imageUrl) return;

    try {
      // Convert data URL to blob
      const response = await fetch(imageUrl);
      const blob = await response.blob();

      await navigator.clipboard.write([
        new ClipboardItem({ 'image/png': blob })
      ]);

      alert('Image copied to clipboard! You can paste it directly into social media.');
    } catch (err) {
      console.error('Failed to copy image:', err);
      alert('Failed to copy image. Please download it instead.');
    }
  };

  const closeModal = () => {
    setShowImageModal(false);
    setImageUrl(null);
  };

  return (
    <>
      <div className="share-buttons">
        <span className="share-label">Share:</span>

        {/* Generate Image Button */}
        {reportRef && (
          <button
            className={`share-btn image ${generating ? 'generating' : ''}`}
            onClick={generateReportImage}
            title="Generate shareable image"
            aria-label="Generate shareable image"
            disabled={generating}
          >
            {generating ? (
              <div className="btn-spinner"></div>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21 15 16 10 5 21"/>
              </svg>
            )}
          </button>
        )}

        <button
          className="share-btn twitter"
          onClick={handleTwitterShare}
          title="Share on Twitter"
          aria-label="Share on Twitter"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
          </svg>
        </button>

        <button
          className="share-btn facebook"
          onClick={handleFacebookShare}
          title="Share on Facebook"
          aria-label="Share on Facebook"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
          </svg>
        </button>

        <button
          className="share-btn linkedin"
          onClick={handleLinkedInShare}
          title="Share on LinkedIn"
          aria-label="Share on LinkedIn"
        >
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
          </svg>
        </button>

        <button
          className="share-btn email"
          onClick={handleEmailShare}
          title="Share via Email"
          aria-label="Share via Email"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
          </svg>
        </button>

        <button
          className={`share-btn copy ${copied ? 'copied' : ''}`}
          onClick={handleCopyLink}
          title={copied ? 'Copied!' : 'Copy link'}
          aria-label="Copy link"
        >
          {copied ? (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
          )}
        </button>
      </div>

      {/* Image Preview Modal */}
      {showImageModal && imageUrl && (
        <div className="image-modal-overlay" onClick={closeModal}>
          <div className="image-modal" onClick={e => e.stopPropagation()}>
            <div className="image-modal-header">
              <h3>Report Image</h3>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            <div className="image-modal-content">
              <img src={imageUrl} alt="Property Report" />
            </div>
            <div className="image-modal-actions">
              <button className="btn-primary" onClick={handleDownloadImage}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="7 10 12 15 17 10"/>
                  <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Download Image
              </button>
              <button className="btn-secondary" onClick={handleCopyImage}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                </svg>
                Copy to Clipboard
              </button>
            </div>
            <p className="image-modal-hint">
              Download the image and share it on any social media platform for the full report!
            </p>
          </div>
        </div>
      )}
    </>
  );
};

export default ShareButtons;
