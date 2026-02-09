/**
 * Google Analytics 4 Integration Hook
 *
 * Usage:
 * 1. Add VITE_GA_MEASUREMENT_ID to your .env file
 * 2. The GA script will be automatically loaded when the app starts
 * 3. Use trackEvent() to send custom events
 *
 * Example events:
 * - trackEvent('analysis_started', { address: '123 Main St' })
 * - trackEvent('purchase_completed', { amount: 10, credits: 10 })
 * - trackEvent('referral_shared', { platform: 'twitter' })
 */

declare global {
  interface Window {
    gtag: (...args: any[]) => void;
    dataLayer: any[];
  }
}

const GA_MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID;

let isInitialized = false;

/**
 * Initialize Google Analytics 4
 * Call this once when the app starts (in App.tsx or main.tsx)
 */
export function initializeGA(): void {
  if (isInitialized || !GA_MEASUREMENT_ID) {
    return;
  }

  // Create script element for gtag.js
  const script = document.createElement('script');
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
  document.head.appendChild(script);

  // Initialize dataLayer and gtag function
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };

  window.gtag('js', new Date());
  window.gtag('config', GA_MEASUREMENT_ID, {
    send_page_view: false, // We'll send page views manually for SPA
  });

  isInitialized = true;
  console.log('Google Analytics 4 initialized');
}

/**
 * Track a page view
 * Call this when the route changes
 */
export function trackPageView(path: string, title?: string): void {
  if (!GA_MEASUREMENT_ID || !window.gtag) return;

  window.gtag('event', 'page_view', {
    page_path: path,
    page_title: title || document.title,
  });
}

/**
 * Track a custom event
 */
export function trackEvent(
  eventName: string,
  params?: Record<string, string | number | boolean>
): void {
  if (!GA_MEASUREMENT_ID || !window.gtag) return;

  window.gtag('event', eventName, params);
}

/**
 * Set user properties (for logged-in users)
 */
export function setUserProperties(userId: string, properties?: Record<string, any>): void {
  if (!GA_MEASUREMENT_ID || !window.gtag) return;

  window.gtag('config', GA_MEASUREMENT_ID, {
    user_id: userId,
    ...properties,
  });
}

/**
 * React hook for analytics
 */
export function useAnalytics() {
  return {
    trackEvent,
    trackPageView,
    setUserProperties,
  };
}

// Predefined event names for consistency
export const AnalyticsEvents = {
  // User events
  SIGN_UP: 'sign_up',
  LOGIN: 'login',
  LOGOUT: 'logout',

  // Analysis events
  ANALYSIS_STARTED: 'analysis_started',
  ANALYSIS_COMPLETED: 'analysis_completed',
  ANALYSIS_SHARED: 'analysis_shared',

  // Purchase events
  PURCHASE_STARTED: 'purchase_started',
  PURCHASE_COMPLETED: 'purchase_completed',

  // Engagement events
  FAVORITE_ADDED: 'favorite_added',
  FAVORITE_REMOVED: 'favorite_removed',
  DOCUMENT_UPLOADED: 'document_uploaded',
  CHAT_MESSAGE_SENT: 'chat_message_sent',

  // Referral events
  REFERRAL_LINK_COPIED: 'referral_link_copied',
  REFERRAL_SHARED: 'referral_shared',

  // Survey events
  SURVEY_STARTED: 'survey_started',
  SURVEY_COMPLETED: 'survey_completed',
} as const;

export default useAnalytics;
