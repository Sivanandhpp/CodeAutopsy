/**
 * Landing Page — Custom design with DotGrid, LiquidBlobs, and GlassInput
 * Auth panel opens from login button.
 */

import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { analyzeRepository } from '../lib/api';
import useAnalysisStore from '../lib/analysisStore';
import useAuthStore from '../lib/authStore';
import AuthPanel from '../components/auth/AuthPanel';

import DotGrid from '../components/landing/DotGrid';
import LiquidBlobs from '../components/landing/LiquidBlobs';

export default function LandingPage() {
  const loginBtnRef = useRef(null);
  const [showAuth, setShowAuth] = useState(false);
  const { isAuthenticated } = useAuthStore();
  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setAnalysisId, setAnalysisStatus } = useAnalysisStore();

  const handleAnalyze = async (e) => {
    if (e) e.preventDefault();
    setError('');

    const url = repoUrl.trim();
    if (!url) return;

    // Validate GitHub URL
    const urlPattern = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/;
    if (!urlPattern.test(url.replace(/\.git$/, ''))) {
      setError('Please enter a valid GitHub URL (e.g., https://github.com/owner/repo)');
      return;
    }

    setLoading(true);
    try {
      const data = await analyzeRepository(url);
      setAnalysisId(data.analysis_id);
      setAnalysisStatus('analyzing');
      navigate(`/analysis/${data.analysis_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start analysis. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  const handlePaste = useCallback(async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setRepoUrl(text);
        setError('');
      }
    } catch {
      // Clipboard permission denied — ignore silently
    }
  }, []);

  const handleTryJuiceShop = useCallback(() => {
    setRepoUrl('https://github.com/juice-shop/juice-shop');
    setError('');
  }, []);

  return (
    <div className="lp-container">
      <DotGrid />
      <LiquidBlobs />

      <div className="lp-layout">
        {/* Header */}
        <header className="lp-header">
          <div className="lp-logo">
            <span className="lp-logo-text">CodeAutopsy</span>
            <span className="lp-badge">BETA</span>
          </div>
          <button ref={loginBtnRef} className="lp-login-btn" onClick={() => setShowAuth(true)}>
            {isAuthenticated ? 'Dashboard' : 'Login'}
          </button>
        </header>

        {/* Auth Panel */}
        <AuthPanel isOpen={showAuth} onClose={() => setShowAuth(false)} anchorRef={loginBtnRef} />

        {/* Main Hero */}
        <main className="lp-main">
          <motion.h1
            className="lp-hero-text"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
          >
            Bugs don't appear.<br />They're introduced.

          </motion.h1>

          <motion.p
            className="lp-sub-hero"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.35 }}
          >
            Catch bugs at their origin before they ship.
          </motion.p>

          {/* Glass Input */}
          <motion.form
            className="lp-glass-container"
            onSubmit={handleAnalyze}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.55 }}
          >
            <div className="lp-glass-wrapper">
              <input
                type="text"
                className="lp-glass-field"
                placeholder="Paste a GitHub repository URL..."
                value={repoUrl}
                onChange={(e) => { setRepoUrl(e.target.value); setError(''); }}
                disabled={loading}
              />

              {/* Paste button */}
              <button
                type="button"
                className="lp-btn-ghost"
                onClick={handlePaste}
                title="Paste from clipboard"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
              </button>

              {/* Analyze button */}
              <button
                type="submit"
                className="lp-btn-primary"
                disabled={loading || !repoUrl.trim()}
              >
                {loading ? (
                  <div className="lp-spinner" />
                ) : (
                  'Analyse'
                )}
              </button>
            </div>

            {/* Error message */}
            {error && (
              <motion.p
                className="lp-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
              >
                {error}
              </motion.p>
            )}

            {/* Try hint */}
            <div className="lp-glass-hint">
              Try:{' '}
              <button
                type="button"
                className="lp-hint-link"
                onClick={handleTryJuiceShop}
              >
                juice-shop/juice-shop
              </button>
            </div>
          </motion.form>
        </main>
      </div>

      <style>{landingStyles}</style>
    </div>
  );
}

const landingStyles = `
  .lp-container {
    width: 100vw;
    min-height: 100vh;
    position: relative;
    overflow: hidden;
    background-color: #000;
  }

  .lp-layout {
    position: relative;
    z-index: 10;
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    width: 100%;
  }

  /* ─── Header ─────────────────────── */
  .lp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem 3rem;
  }

  .lp-logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .lp-logo-text {
    font-size: 1.25rem;
    font-weight: 500;
    color: white;
    letter-spacing: -0.5px;
  }

  .lp-badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    color: rgba(255, 255, 255, 0.8);
    font-weight: 500;
    letter-spacing: 0.5px;
  }

  .lp-login-btn {
    background-color: white;
    color: black;
    border: none;
    padding: 0.4rem 1.2rem;
    border-radius: 20px;
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: inherit;
  }

  .lp-login-btn:hover {
    background-color: #eee;
    transform: scale(1.05);
  }

  /* ─── Main ───────────────────────── */
  .lp-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
    margin-top: 5vh;
  }

  .lp-hero-text {
    font-size: clamp(3rem, 7vw, 6rem);
    font-weight: 800;
    line-height: 1.1;
    color: white;
    margin-bottom: 2rem;
    letter-spacing: -4px;
    text-shadow: 0 0 40px rgba(255, 255, 255, 0.3);
  }

  .lp-sub-hero {
    font-size: 1.2rem;
    color: rgba(255, 255, 255, 0.8);
    margin-bottom: 6rem;
    max-width: 600px;
  }

  /* ─── Glass Input ────────────────── */
  .lp-glass-container {
    position: relative;
    z-index: 10;
    margin-top: auto;
    margin-bottom: 80px;
    align-self: center;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
    width: 100%;
    max-width: 700px;
  }

  .lp-glass-wrapper {
    padding: 0.6rem 0.6rem 0.6rem 1.75rem;
    border-radius: 20px;
    background-color: rgba(30, 33, 48, 0.5);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    width: 100%;
    transition: border-color 0.2s;
  }

  .lp-glass-wrapper:focus-within {
    border-color: rgba(99, 102, 241, 0.4);
  }

  .lp-glass-field {
    background: transparent;
    border: none;
    outline: none;
    color: white;
    flex: 1;
    font-size: 1.15rem;
    font-family: inherit;
    margin-left: 0;
    caret-color: #f9d857;
  }

  .lp-glass-field::placeholder {
    color: #a0a0ab;
    font-weight: 400;
    letter-spacing: -0.2px;
  }

  .lp-glass-field:disabled {
    opacity: 0.5;
  }

  .lp-btn-ghost {
    background: transparent;
    border: none;
    color: #a0a0ab;
    font-size: 0.95rem;
    font-family: inherit;
    cursor: pointer;
    padding: 0.5rem 0.8rem;
    transition: color 0.2s;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .lp-btn-ghost:hover {
    color: white;
  }

  .lp-btn-primary {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 0.65rem 1.2rem;
    color: white;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.95rem;
    font-family: inherit;
    cursor: pointer;
    margin-left: 0.5rem;
    transition: background-color 0.2s ease;
  }

  .lp-btn-primary:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.2);
  }

  .lp-btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .lp-spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: lp-spin 0.6s linear infinite;
  }

  @keyframes lp-spin {
    to { transform: rotate(360deg); }
  }

  .lp-error {
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.85rem;
    align-self: center;
    margin-top: 0.3rem;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  }

  .lp-glass-hint {
    color: rgba(255, 255, 255, 0.85);
    font-size: 0.9rem;
    align-self: center;
    margin-top: 0.1rem;
    font-weight: 500;
    letter-spacing: 0.3px;
    position: relative;
    z-index: 20;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
  }

  .lp-hint-link {
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.85);
    cursor: pointer;
    font-size: inherit;
    font-family: var(--ca-font-mono, monospace);
    text-decoration: underline;
    text-underline-offset: 3px;
    font-weight: 500;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
    transition: color 0.2s;
  }

  .lp-hint-link:hover {
    color: #a78bfa;
  }

  /* ─── Responsive ─────────────────── */
  @media (max-width: 640px) {
    .lp-header { padding: 1rem 1.5rem; }
    .lp-main { padding: 1rem; }
    .lp-glass-container { max-width: 95%; }
    .lp-hero-text { letter-spacing: -1px; }
    .lp-sub-hero { margin-bottom: 3rem; font-size: 1rem; }
  }
`;
