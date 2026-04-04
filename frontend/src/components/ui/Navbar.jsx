/**
 * Navbar — Top navigation bar with auth state awareness
 * Shows login button for guests, user avatar + dashboard link for authenticated users.
 */

import { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sun, Moon, LogOut, LayoutDashboard } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import useThemeStore from '../../lib/themeStore';
import useAuthStore from '../../lib/authStore';
import AuthPanel from '../auth/AuthPanel';

export default function Navbar() {
  const { theme, toggleTheme } = useThemeStore();
  const { isAuthenticated, user, logout } = useAuthStore();
  const [showAuth, setShowAuth] = useState(false);
  const loginBtnRef = useRef(null);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="ca-nav">
      <div className="ca-nav-inner">
        {/* Logo */}
        <Link to={isAuthenticated ? '/dashboard' : '/'} className="ca-nav-brand">
          <span className="ca-nav-logo">CodeAutopsy</span>
          <span className="ca-nav-badge">v2.0</span>
        </Link>

        {/* Right Actions */}
        <div className="ca-nav-actions">
          {/* Theme Toggle */}
          <motion.button
            className="ca-nav-theme"
            onClick={toggleTheme}
            whileTap={{ scale: 0.9 }}
            whileHover={{ scale: 1.1 }}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={theme}
                initial={{ y: -14, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 14, opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
              </motion.div>
            </AnimatePresence>
          </motion.button>

          {isAuthenticated ? (
            /* Authenticated — show user info */
            <>
              <Link to="/dashboard" className="ca-nav-dashboard" title="Dashboard">
                <LayoutDashboard size={16} />
              </Link>

              <div className="ca-nav-user">
                <div className="ca-nav-avatar">
                  {user?.username?.charAt(0).toUpperCase() || '?'}
                </div>
                <span className="ca-nav-username">{user?.username}</span>
              </div>

              <button className="ca-nav-logout" onClick={handleLogout} title="Sign out">
                <LogOut size={14} />
              </button>
            </>
          ) : (
            /* Guest — show login button */
            <button
              ref={loginBtnRef}
              className="ca-nav-login"
              onClick={() => setShowAuth(true)}
            >
              Login
            </button>
          )}
        </div>
      </div>

      {/* Floating Auth Panel */}
      <AuthPanel
        isOpen={showAuth}
        onClose={() => setShowAuth(false)}
        anchorRef={loginBtnRef}
      />

      <style>{`
        .ca-nav {
          position: relative;
          z-index: 50;
          border-bottom: 1px solid var(--ca-border);
          background: var(--ca-bg);
        }
        .ca-nav-inner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          max-width: 1280px;
          margin: 0 auto;
          padding: 1rem 2rem;
        }
        .ca-nav-brand {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          text-decoration: none;
          color: var(--ca-text);
        }
        .ca-nav-logo {
          font-size: 1.15rem;
          font-weight: 600;
          letter-spacing: -0.5px;
        }
        .ca-nav-badge {
          font-size: 0.65rem;
          padding: 0.1rem 0.45rem;
          border-radius: 10px;
          border: 1px solid var(--ca-border);
          color: var(--ca-text-muted);
          font-weight: 500;
          letter-spacing: 0.5px;
        }
        .ca-nav-actions {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .ca-nav-theme {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 18px;
          border: 1px solid var(--ca-border);
          background: var(--ca-bg-secondary);
          color: var(--ca-text);
          cursor: pointer;
          transition: border-color 0.2s;
        }
        .ca-nav-theme:hover {
          border-color: var(--ca-primary);
        }
        .ca-nav-login {
          background: var(--ca-text);
          color: var(--ca-bg);
          border: none;
          padding: 0.35rem 1rem;
          border-radius: 18px;
          font-weight: 500;
          font-size: 0.85rem;
          cursor: pointer;
          transition: opacity 0.2s;
          font-family: inherit;
        }
        .ca-nav-login:hover {
          opacity: 0.85;
        }

        /* Authenticated user elements */
        .ca-nav-dashboard {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 18px;
          border: 1px solid var(--ca-border);
          background: var(--ca-bg-secondary);
          color: var(--ca-text-muted);
          text-decoration: none;
          transition: all 0.15s;
        }
        .ca-nav-dashboard:hover {
          border-color: var(--ca-primary);
          color: var(--ca-primary);
        }

        .ca-nav-user {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .ca-nav-avatar {
          width: 30px;
          height: 30px;
          border-radius: 50%;
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.8rem;
          font-weight: 600;
        }
        .ca-nav-username {
          font-size: 0.88rem;
          color: var(--ca-text);
          font-weight: 500;
        }

        .ca-nav-logout {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 30px;
          height: 30px;
          border-radius: 18px;
          border: 1px solid var(--ca-border);
          background: transparent;
          color: var(--ca-text-muted);
          cursor: pointer;
          transition: all 0.15s;
        }
        .ca-nav-logout:hover {
          border-color: #ef4444;
          color: #ef4444;
          background: rgba(239, 68, 68, 0.08);
        }

        @media (max-width: 480px) {
          .ca-nav-username { display: none; }
        }
      `}</style>
    </nav>
  );
}
