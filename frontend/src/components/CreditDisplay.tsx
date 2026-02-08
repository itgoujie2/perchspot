import { useLocation, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function CreditDisplay() {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();

  // Hide on chat page — it has its own header with credits
  if (!isAuthenticated || !user || location.pathname === '/chat') return null;

  return (
    <div style={{
      position: 'fixed',
      top: 12,
      right: 16,
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem',
      background: 'rgba(0,0,0,0.6)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      padding: '0.4rem 0.85rem',
      borderRadius: '10px',
      color: 'white',
      fontSize: '0.85rem',
      fontFamily: '-apple-system, BlinkMacSystemFont, sans-serif',
    }}>
      <span style={{ opacity: 0.7 }}>{user.email}</span>
      <span style={{ fontWeight: 600 }}>${user.credit_balance.toFixed(2)}</span>
      <Link
        to="/credits"
        style={{
          color: '#667eea',
          textDecoration: 'none',
          fontSize: '0.75rem',
          fontWeight: 600,
          background: 'rgba(102,126,234,0.15)',
          padding: '0.15rem 0.5rem',
          borderRadius: '6px',
        }}
      >
        Buy Credits
      </Link>
      <button
        onClick={logout}
        style={{
          background: 'none',
          border: '1px solid rgba(255,255,255,0.3)',
          color: 'rgba(255,255,255,0.7)',
          padding: '0.15rem 0.5rem',
          borderRadius: '6px',
          cursor: 'pointer',
          fontSize: '0.75rem',
        }}
      >
        Logout
      </button>
    </div>
  );
}
