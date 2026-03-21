/**
 * Navbar Component
 * Top navigation bar with branding, theme toggle, and navigation links.
 */

import { Link, useLocation } from 'react-router-dom';
import { Sun, Moon, Github, Microscope } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import useThemeStore from '../../lib/themeStore';

export default function Navbar() {
  const { theme, toggleTheme } = useThemeStore();
  const location = useLocation();
  
  const isActive = (path) => location.pathname === path;
  
  return (
    <nav className="navbar">
      <div className="container navbar-inner">
        {/* Logo */}
        <Link to="/" className="navbar-brand">
          <div className="navbar-logo-icon">
            <Microscope size={22} />
          </div>
          <span className="navbar-logo-text">
            Code<span className="gradient-text">Autopsy</span>
          </span>
        </Link>
        
        {/* Navigation Links */}
        <div className="navbar-links">
          <Link 
            to="/" 
            className={`navbar-link ${isActive('/') ? 'active' : ''}`}
          >
            Home
          </Link>
        </div>
        
        {/* Actions */}
        <div className="navbar-actions">
          <motion.button
            className="theme-toggle"
            onClick={toggleTheme}
            whileTap={{ scale: 0.9 }}
            whileHover={{ scale: 1.1 }}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
          >
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={theme}
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 20, opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
              </motion.div>
            </AnimatePresence>
          </motion.button>
          
          <a
            href="https://github.com"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ padding: '8px 14px', fontSize: '0.85rem' }}
          >
            <Github size={16} />
            <span className="hide-mobile">GitHub</span>
          </a>
        </div>
      </div>
      
      <style>{`
        .navbar {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          background: var(--ca-glass-bg);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border-bottom: 1px solid var(--ca-glass-border);
        }
        
        .navbar-inner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: 64px;
          gap: 24px;
        }
        
        .navbar-brand {
          display: flex;
          align-items: center;
          gap: 10px;
          text-decoration: none;
          color: var(--ca-text);
          font-weight: 700;
          font-size: 1.2rem;
        }
        
        .navbar-logo-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 10px;
          background: var(--ca-gradient-primary);
          color: white;
        }
        
        .navbar-logo-text {
          font-size: 1.2rem;
          font-weight: 800;
          letter-spacing: -0.02em;
        }
        
        .navbar-links {
          display: flex;
          gap: 8px;
        }
        
        .navbar-link {
          text-decoration: none;
          color: var(--ca-text-secondary);
          font-weight: 500;
          font-size: 0.9rem;
          padding: 6px 14px;
          border-radius: 8px;
          transition: all 0.2s;
        }
        
        .navbar-link:hover,
        .navbar-link.active {
          color: var(--ca-text);
          background: rgba(99, 102, 241, 0.1);
        }
        
        .navbar-actions {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        
        .theme-toggle {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 10px;
          border: 1px solid var(--ca-border);
          background: var(--ca-bg-elevated);
          color: var(--ca-text);
          cursor: pointer;
          transition: all 0.2s;
        }
        
        .theme-toggle:hover {
          border-color: var(--ca-primary);
          background: rgba(99, 102, 241, 0.1);
        }
        
        @media (max-width: 640px) {
          .hide-mobile { display: none; }
          .navbar-links { display: none; }
        }
      `}</style>
    </nav>
  );
}
