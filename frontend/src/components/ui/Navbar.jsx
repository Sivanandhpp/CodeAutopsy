/**
 * Navbar — Simple scrollable navbar matching landing page style
 * Left: CodeAutopsy + BETA badge
 * Right: Theme toggle + Login button
 */

import { Link } from 'react-router-dom';
import { Sun, Moon } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import useThemeStore from '../../lib/themeStore';

export default function Navbar() {
  const { theme, toggleTheme } = useThemeStore();

  return (
    <nav className="ca-nav">
      <div className="ca-nav-inner">
        {/* Logo */}
        <Link to="/" className="ca-nav-brand">
          <span className="ca-nav-logo">CodeAutopsy</span>
          <span className="ca-nav-badge">BETA</span>
        </Link>

        {/* Right Actions */}
        <div className="ca-nav-actions">
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

          <button className="ca-nav-login">Login</button>
        </div>
      </div>

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
          border-radius: 8px;
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
      `}</style>
    </nav>
  );
}
