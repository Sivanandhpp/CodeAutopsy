/**
 * Landing Page
 * Hero section with GitHub URL input form and feature highlights.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Search, GitBranch, Shield, Brain, 
  ChevronRight, Zap, Clock, Code2,
  ArrowRight, Sparkles, Activity, Eye
} from 'lucide-react';
import { analyzeRepository } from '../lib/api';
import useAnalysisStore from '../lib/analysisStore';

export default function LandingPage() {
  const [repoUrl, setRepoUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { setAnalysisId, setAnalysisStatus } = useAnalysisStore();
  
  const handleAnalyze = async (e) => {
    e.preventDefault();
    setError('');
    
    // Validate GitHub URL
    const urlPattern = /^https?:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/;
    if (!urlPattern.test(repoUrl.trim().replace(/\.git$/, ''))) {
      setError('Please enter a valid GitHub URL (e.g., https://github.com/owner/repo)');
      return;
    }
    
    setLoading(true);
    try {
      const data = await analyzeRepository(repoUrl.trim());
      setAnalysisId(data.analysis_id);
      setAnalysisStatus('analyzing');
      navigate(`/analysis/${data.analysis_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start analysis. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero">
        {/* Animated background elements */}
        <div className="hero-bg-effects">
          <div className="hero-orb hero-orb-1" />
          <div className="hero-orb hero-orb-2" />
          <div className="hero-orb hero-orb-3" />
          <div className="hero-grid" />
        </div>
        
        <div className="container hero-content">
          <motion.div
            className="hero-badge"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <Sparkles size={14} />
            <span>AI-Powered Code Archaeology</span>
          </motion.div>
          
          <motion.h1
            className="hero-title"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            A Time Machine for{' '}
            <span className="gradient-text">Debugging</span>
          </motion.h1>
          
          <motion.p
            className="hero-subtitle"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            Don't just find bugs — discover <strong>when</strong> they were introduced, 
            <strong> who</strong> wrote them, and <strong>how</strong> they evolved. 
            CodeAutopsy combines security scanning with Git forensics and AI insights.
          </motion.p>
          
          {/* Analysis Form */}
          <motion.form
            className="hero-form"
            onSubmit={handleAnalyze}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <div className="hero-input-wrapper">
              <Search size={20} className="hero-input-icon" />
              <input
                type="text"
                className="hero-input"
                placeholder="Paste a GitHub repository URL..."
                value={repoUrl}
                onChange={(e) => { setRepoUrl(e.target.value); setError(''); }}
                disabled={loading}
              />
              <button
                type="submit"
                className="hero-submit-btn"
                disabled={loading || !repoUrl.trim()}
              >
                {loading ? (
                  <div className="spinner" />
                ) : (
                  <>
                    <span>Analyze</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </div>
            
            {error && (
              <motion.p
                className="hero-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
              >
                {error}
              </motion.p>
            )}
            
            <p className="hero-hint">
              Try: <button type="button" className="hero-hint-link" onClick={() => setRepoUrl('https://github.com/juice-shop/juice-shop')}>
                juice-shop/juice-shop
              </button>
            </p>
          </motion.form>
        </div>
      </section>
      
      {/* Features Section */}
      <section className="features">
        <div className="container">
          <motion.div
            className="features-grid"
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={{
              hidden: {},
              visible: { transition: { staggerChildren: 0.1 } }
            }}
          >
            {features.map((feature, index) => (
              <motion.div
                key={index}
                className="feature-card card"
                variants={{
                  hidden: { opacity: 0, y: 20 },
                  visible: { opacity: 1, y: 0 }
                }}
              >
                <div className="feature-icon" style={{ background: feature.color }}>
                  {feature.icon}
                </div>
                <h3 className="feature-title">{feature.title}</h3>
                <p className="feature-desc">{feature.description}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>
      
      {/* How It Works Section */}
      <section className="how-it-works">
        <div className="container">
          <h2 className="section-title">
            How It <span className="gradient-text">Works</span>
          </h2>
          <div className="steps-grid">
            {steps.map((step, index) => (
              <motion.div
                key={index}
                className="step-card glass-card"
                initial={{ opacity: 0, x: index % 2 === 0 ? -20 : 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
              >
                <div className="step-number">{String(index + 1).padStart(2, '0')}</div>
                <div className="step-content">
                  <h4>{step.title}</h4>
                  <p>{step.description}</p>
                </div>
                {index < steps.length - 1 && <ChevronRight className="step-arrow" size={20} />}
              </motion.div>
            ))}
          </div>
        </div>
      </section>
      
      <style>{`
        .landing-page {
          min-height: 100vh;
        }
        
        /* ─── Hero ─────────────────────────────── */
        
        .hero {
          position: relative;
          min-height: 85vh;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          padding-top: 80px;
        }
        
        .hero-bg-effects {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }
        
        .hero-orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.3;
        }
        
        .hero-orb-1 {
          width: 400px;
          height: 400px;
          background: var(--ca-primary);
          top: 10%;
          left: 15%;
          animation: float 8s ease-in-out infinite;
        }
        
        .hero-orb-2 {
          width: 300px;
          height: 300px;
          background: var(--ca-accent);
          bottom: 20%;
          right: 15%;
          animation: float 6s ease-in-out infinite reverse;
        }
        
        .hero-orb-3 {
          width: 200px;
          height: 200px;
          background: #8b5cf6;
          top: 40%;
          right: 30%;
          animation: float 10s ease-in-out infinite;
        }
        
        .hero-grid {
          position: absolute;
          inset: 0;
          background-image: 
            linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px);
          background-size: 60px 60px;
        }
        
        .hero-content {
          position: relative;
          text-align: center;
          max-width: 800px;
          margin: 0 auto;
        }
        
        .hero-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 16px;
          border-radius: 9999px;
          background: rgba(99, 102, 241, 0.1);
          border: 1px solid rgba(99, 102, 241, 0.2);
          color: var(--ca-primary-light);
          font-size: 0.85rem;
          font-weight: 500;
          margin-bottom: 24px;
        }
        
        .hero-title {
          font-size: clamp(2.5rem, 6vw, 4.2rem);
          font-weight: 900;
          line-height: 1.1;
          margin-bottom: 20px;
          letter-spacing: -0.03em;
        }
        
        .hero-subtitle {
          font-size: 1.15rem;
          color: var(--ca-text-secondary);
          line-height: 1.7;
          margin-bottom: 40px;
          max-width: 640px;
          margin-left: auto;
          margin-right: auto;
        }
        
        .hero-subtitle strong {
          color: var(--ca-text);
        }
        
        .hero-form {
          max-width: 600px;
          margin: 0 auto;
        }
        
        .hero-input-wrapper {
          display: flex;
          align-items: center;
          background: var(--ca-bg-card);
          border: 1px solid var(--ca-border);
          border-radius: 14px;
          padding: 6px;
          transition: all 0.3s;
          box-shadow: var(--ca-shadow-lg);
        }
        
        .hero-input-wrapper:focus-within {
          border-color: var(--ca-primary);
          box-shadow: var(--ca-shadow-glow);
        }
        
        .hero-input-icon {
          color: var(--ca-text-muted);
          margin: 0 12px;
          flex-shrink: 0;
        }
        
        .hero-input {
          flex: 1;
          background: transparent;
          border: none;
          outline: none;
          font-size: 0.95rem;
          color: var(--ca-text);
          font-family: var(--ca-font-sans);
          min-width: 0;
        }
        
        .hero-input::placeholder {
          color: var(--ca-text-muted);
        }
        
        .hero-submit-btn {
          flex-shrink: 0;
          display: flex;
          align-items: center;
          gap: 8px;
          background: var(--ca-gradient-primary);
          color: white;
          border: none;
          border-radius: 10px;
          padding: 12px 24px;
          font-weight: 600;
          font-size: 0.95rem;
          cursor: pointer;
          transition: all 0.2s;
          font-family: var(--ca-font-sans);
        }
        
        .hero-submit-btn:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
        }
        
        .hero-submit-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.6s linear infinite;
        }
        
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        
        .hero-error {
          color: var(--ca-critical);
          font-size: 0.85rem;
          margin-top: 12px;
          text-align: left;
          padding: 0 8px;
        }
        
        .hero-hint {
          color: var(--ca-text-muted);
          font-size: 0.85rem;
          margin-top: 16px;
        }
        
        .hero-hint-link {
          background: none;
          border: none;
          color: var(--ca-primary-light);
          cursor: pointer;
          font-size: inherit;
          font-family: var(--ca-font-mono);
          text-decoration: underline;
          text-underline-offset: 3px;
        }
        
        .hero-hint-link:hover {
          color: var(--ca-primary);
        }
        
        /* ─── Features ─────────────────────────── */
        
        .features {
          padding: 80px 0;
        }
        
        .features-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 24px;
        }
        
        .feature-card {
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 28px;
        }
        
        .feature-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
        }
        
        .feature-title {
          font-size: 1.1rem;
          font-weight: 700;
        }
        
        .feature-desc {
          color: var(--ca-text-secondary);
          font-size: 0.9rem;
          line-height: 1.6;
        }
        
        /* ─── How It Works ─────────────────────── */
        
        .how-it-works {
          padding: 80px 0;
        }
        
        .section-title {
          text-align: center;
          font-size: 2.2rem;
          font-weight: 800;
          letter-spacing: -0.02em;
          margin-bottom: 48px;
        }
        
        .steps-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
        }
        
        .step-card {
          display: flex;
          align-items: flex-start;
          gap: 16px;
          padding: 24px;
          position: relative;
        }
        
        .step-number {
          font-size: 2rem;
          font-weight: 900;
          background: var(--ca-gradient-primary);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          line-height: 1;
          flex-shrink: 0;
        }
        
        .step-content h4 {
          font-size: 1rem;
          font-weight: 700;
          margin-bottom: 4px;
        }
        
        .step-content p {
          font-size: 0.85rem;
          color: var(--ca-text-secondary);
          line-height: 1.5;
        }
        
        .step-arrow {
          position: absolute;
          right: -12px;
          top: 50%;
          transform: translateY(-50%);
          color: var(--ca-text-muted);
          display: none;
        }
        
        @media (min-width: 768px) {
          .step-arrow { display: block; }
        }
        
        @media (max-width: 640px) {
          .hero-submit-btn span { display: none; }
          .hero-submit-btn { padding: 12px 16px; }
        }
      `}</style>
    </div>
  );
}

// Feature cards data
const features = [
  {
    icon: <Shield size={24} />,
    title: 'Multi-Layer Bug Detection',
    description: 'Semgrep security scanning finds SQL injection, XSS, and weak crypto across Python, JavaScript, Java, and TypeScript.',
    color: 'linear-gradient(135deg, #ef4444, #f97316)',
  },
  {
    icon: <Clock size={24} />,
    title: 'Code Archaeology Timeline',
    description: 'Click any bug to see the exact commit that introduced it, with an interactive D3.js timeline showing its evolution.',
    color: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  },
  {
    icon: <Brain size={24} />,
    title: 'AI-Powered Fix Suggestions',
    description: 'Groq AI explains root causes, generates code patches with confidence scoring, and provides step-by-step fix strategies.',
    color: 'linear-gradient(135deg, #06b6d4, #10b981)',
  },
  {
    icon: <Code2 size={24} />,
    title: 'In-Browser IDE',
    description: 'Monaco Editor with squiggly underlines, hover tooltips, and a VS Code-style problems panel for seamless debugging.',
    color: 'linear-gradient(135deg, #8b5cf6, #ec4899)',
  },
  {
    icon: <Eye size={24} />,
    title: 'Blame Heatmap',
    description: 'Visualize author contributions with color-coded ownership. See who touched buggy code and when.',
    color: 'linear-gradient(135deg, #f97316, #eab308)',
  },
  {
    icon: <Activity size={24} />,
    title: 'Health Score & Metrics',
    description: '0-100 health grade with severity distribution charts, before/after comparisons, and dependency graphs.',
    color: 'linear-gradient(135deg, #10b981, #06b6d4)',
  },
];

// How it works steps
const steps = [
  {
    title: 'Paste GitHub URL',
    description: 'Enter any public repository URL to start the analysis.',
  },
  {
    title: 'Automated Scanning',
    description: 'Semgrep + custom analyzers scan for security vulnerabilities.',
  },
  {
    title: 'View Results',
    description: 'Interactive dashboard with health score and issue details.',
  },
  {
    title: 'Explore Archaeology',
    description: 'Timeline shows when bugs were born and how they evolved.',
  },
  {
    title: 'AI Explains & Fixes',
    description: 'Get root cause analysis and code patches with confidence scores.',
  },
];
