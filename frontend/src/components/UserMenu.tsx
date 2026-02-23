import { useState, useRef, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export default function UserMenu() {
  const { user, isAuthenticated, logout } = useAuth();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside - must be called before any conditional returns
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Hide on chat page (has its own header), auth pages (redundant), and admin page (has its own UI)
  if (location.pathname === '/chat' || location.pathname === '/login' || location.pathname === '/register' || location.pathname.startsWith('/admin')) {
    return null;
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="user-menu-container">
        <div className="user-menu-auth-buttons">
          <Link to="/login" className="user-menu-auth-btn login">Sign In</Link>
          <Link to="/register" className="user-menu-auth-btn register">Sign Up</Link>
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div className="user-menu-container" ref={menuRef}>
      <button className="user-menu-trigger" onClick={() => setIsOpen(!isOpen)}>
        <div className="user-avatar">
          {user.email.charAt(0).toUpperCase()}
        </div>
        <div className="user-info">
          <span className="user-email">{user.email}</span>
          <span className="user-credits">${user.credit_balance.toFixed(2)} credits</span>
        </div>
        <svg className={`chevron ${isOpen ? 'open' : ''}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="6,9 12,15 18,9" />
        </svg>
      </button>

      {isOpen && (
        <div className="user-menu-dropdown">
          <div className="menu-section">
            <Link to="/account" className="menu-item" onClick={() => setIsOpen(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              My Account
            </Link>
            <Link to="/account?tab=favorites" className="menu-item" onClick={() => setIsOpen(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
              Favorites
            </Link>
            <Link to="/account?tab=history" className="menu-item" onClick={() => setIsOpen(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12,6 12,12 16,14" />
              </svg>
              Analysis History
            </Link>
          </div>
          <div className="menu-divider" />
          <div className="menu-section">
            <Link to="/credits" className="menu-item" onClick={() => setIsOpen(false)}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                <line x1="1" y1="10" x2="23" y2="10" />
              </svg>
              Buy Credits
            </Link>
          </div>
          <div className="menu-divider" />
          <div className="menu-section">
            <button className="menu-item logout" onClick={() => { logout(); setIsOpen(false); }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16,17 21,12 16,7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      )}
      <style>{styles}</style>
    </div>
  );
}

const styles = `
.user-menu-container {
  position: fixed;
  top: 12px;
  right: 16px;
  z-index: 1000;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.user-menu-auth-buttons {
  display: flex;
  gap: 0.5rem;
}

.user-menu-auth-btn {
  padding: 0.5rem 1.25rem;
  border-radius: 20px;
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.user-menu-auth-btn.login {
  color: white;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.user-menu-auth-btn.login:hover {
  background: rgba(255, 255, 255, 0.25);
}

.user-menu-auth-btn.register {
  color: white;
  background: rgba(255, 255, 255, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.user-menu-auth-btn.register:hover {
  background: rgba(255, 255, 255, 0.35);
}

.user-menu-trigger {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  background: white;
  border: 1px solid #e2e8f0;
  padding: 0.5rem 0.75rem;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.user-menu-trigger:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
}

.user-email {
  font-size: 0.8rem;
  color: #334155;
  font-weight: 500;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-credits {
  font-size: 0.7rem;
  color: #667eea;
  font-weight: 600;
}

.chevron {
  width: 16px;
  height: 16px;
  color: #94a3b8;
  transition: transform 0.2s;
}

.chevron.open {
  transform: rotate(180deg);
}

.user-menu-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.15);
  min-width: 220px;
  overflow: hidden;
  animation: slideDown 0.15s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.menu-section {
  padding: 0.5rem;
}

.menu-divider {
  height: 1px;
  background: #f1f5f9;
  margin: 0;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
  color: #334155;
  text-decoration: none;
  font-size: 0.875rem;
  transition: background 0.15s;
  width: 100%;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
}

.menu-item:hover {
  background: #f8fafc;
}

.menu-item svg {
  width: 18px;
  height: 18px;
  color: #64748b;
}

.menu-item.logout {
  color: #dc2626;
}

.menu-item.logout svg {
  color: #dc2626;
}

.menu-item.logout:hover {
  background: #fef2f2;
}

@media (max-width: 480px) {
  .user-info {
    display: none;
  }

  .user-menu-trigger {
    padding: 0.5rem;
  }

  .chevron {
    display: none;
  }
}
`;
