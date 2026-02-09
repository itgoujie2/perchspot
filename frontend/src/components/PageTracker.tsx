import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { trackPageView } from '../hooks/useAnalytics';

/**
 * Component that tracks page views when route changes.
 * Include this inside the Router component.
 */
const PageTracker: React.FC = () => {
  const location = useLocation();

  useEffect(() => {
    // Track page view on route change
    trackPageView(location.pathname + location.search);
  }, [location]);

  return null;
};

export default PageTracker;
