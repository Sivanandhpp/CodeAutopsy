/**
 * Analysis Page — Terminal UI Loading Screen
 * Full-screen command-prompt style loader with progressive progress bar.
 */

import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import { getAnalysisResults } from '../lib/api';
import useAnalysisStore from '../lib/analysisStore';
import ResultsDashboard from '../components/analysis/ResultsDashboard';

import DotGrid from '../components/landing/DotGrid';
import LiquidBlobs from '../components/landing/LiquidBlobs';

// ─── Step → command definitions ────────────────────────────────────────────
const STEP_COMMANDS = {
  queued: {
    cmd: '$ autopsy init --queue',
    lines: [
      { text: 'Connecting to CodeAutopsy engine...', color: 'cyan' },
      { text: 'Job queued successfully.', color: 'green' },
    ],
  },
  clone: {
    cmd: null, // filled dynamically with repo URL
    lines: [
      { text: "remote: Enumerating objects: counting...", color: 'white' },
      { text: "remote: Counting objects: 100%", color: 'white' },
      { text: "Receiving objects: 100% (compressed)", color: 'white' },
      { text: "✓ Repository cloned successfully.", color: 'green' },
    ],
  },
  file_tree: {
    cmd: '$ autopsy tree --extract --index',
    lines: [
      { text: "Scanning directory structure...", color: 'cyan' },
      { text: "Building file index...", color: 'white' },
      { text: "✓ File tree extracted.", color: 'green' },
    ],
  },
  static_analysis: {
    cmd: '$ autopsy scan --deep --secrets --vuln',
    lines: [
      { text: "Running static analysis rules...", color: 'cyan' },
      { text: "⚠ Checking for hardcoded secrets...", color: 'yellow' },
      { text: "⚠ Running OWASP vulnerability checks...", color: 'yellow' },
      { text: "Running dependency audit...", color: 'white' },
      { text: "✓ Security scan complete.", color: 'green' },
    ],
  },
  scoring: {
    cmd: '$ autopsy ai --model gemini --analyze --score',
    lines: [
      { text: "Loading AI model weights...", color: 'cyan' },
      { text: "Running pattern recognition...", color: 'white' },
      { text: "Generating health metrics...", color: 'white' },
      { text: "✓ AI analysis complete.", color: 'green' },
    ],
  },
  complete: {
    cmd: '$ autopsy report --generate',
    lines: [
      { text: "Compiling final report...", color: 'cyan' },
      { text: "✓ Report ready.", color: 'green' },
    ],
  },
};

const STEP_ORDER = ['queued', 'clone', 'file_tree', 'static_analysis', 'scoring', 'complete'];

export default function AnalysisPage() {
  const { id } = useParams();
  const [progress, setProgress] = useState(10);
  const [displayProgress, setDisplayProgress] = useState(10);
  const [currentStep, setCurrentStep] = useState('queued');
  const [error, setError] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const [termLines, setTermLines] = useState([]);
  const [repoUrl, setRepoUrl] = useState('');
  const eventSourceRef = useRef(null);
  const termEndRef = useRef(null);
  const addedStepsRef = useRef(new Set());

  const { analysisResult, setAnalysisResult, setAnalysisId } = useAnalysisStore();

  // Smooth progress animation
  useEffect(() => {
    if (displayProgress < progress) {
      const timer = setTimeout(() => {
        setDisplayProgress(prev => Math.min(prev + 1, progress));
      }, 18);
      return () => clearTimeout(timer);
    }
  }, [displayProgress, progress]);

  // Auto-scroll terminal
  useEffect(() => {
    termEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [termLines]);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (id) {
      setAnalysisId(id);
      // Try to get repo URL from store
      const stored = sessionStorage.getItem('ca_repo_url');
      if (stored) setRepoUrl(stored);
      startStreaming(id);
    }
    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
    };
  }, [id]);

  // Add terminal lines for a step
  const addStepLines = (step, repoUrlOverride) => {
    if (addedStepsRef.current.has(step)) return;
    addedStepsRef.current.add(step);

    const def = STEP_COMMANDS[step];
    if (!def) return;

    let cmd = def.cmd;
    if (step === 'clone') {
      const url = repoUrlOverride || repoUrl || '<repo>';
      cmd = `$ git clone ${url}`;
    }

    const newLines = [];
    if (cmd) newLines.push({ text: cmd, color: 'prompt', isCmd: true });
    newLines.push(...def.lines);

    // Stagger line additions
    newLines.forEach((line, i) => {
      setTimeout(() => {
        setTermLines(prev => [...prev, { ...line, id: `${step}-${i}-${Date.now()}` }]);
      }, i * 120);
    });
  };

  const startStreaming = (analysisId) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const eventSource = new EventSource(`${apiUrl}/api/analyze/stream/${analysisId}`);
    eventSourceRef.current = eventSource;

    // Seed the initial queued lines
    addStepLines('queued');

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const newProgress = data.progress || 0;
        const newStep = data.current_step || 'queued';

        setProgress(newProgress);
        setCurrentStep(newStep);

        // Grab repo URL from message if possible
        if (data.repo_url) {
          setRepoUrl(data.repo_url);
          sessionStorage.setItem('ca_repo_url', data.repo_url);
        }

        addStepLines(newStep, data.repo_url);

        if (data.status === 'complete') {
          eventSource.close();
          setProgress(100);
          addStepLines('complete', data.repo_url);
          setTimeout(() => fetchResults(analysisId), 800);
        } else if (data.status === 'failed') {
          eventSource.close();
          setError(data.message || 'Analysis failed');
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
      fetchResults(analysisId);
    };
  };

  const fetchResults = async (analysisId) => {
    try {
      const data = await getAnalysisResults(analysisId);
      setAnalysisResult(data);
      if (data.status === 'complete') {
        setProgress(100);
        setTimeout(() => setIsComplete(true), 600);
      } else if (data.status === 'failed') {
        setError(data.error_message || 'Analysis failed');
      } else {
        setTimeout(() => fetchResults(analysisId), 3000);
      }
    } catch (err) {
      setError('Failed to fetch results. Please try again.');
    }
  };

  const getProgressColor = (p) => {
    if (p >= 80) return '#10b981';
    if (p >= 50) return '#f59e0b';
    return '#6366f1';
  };

  const getLineColor = (color) => {
    switch (color) {
      case 'green': return '#10b981';
      case 'yellow': return '#f59e0b';
      case 'cyan': return '#06b6d4';
      case 'prompt': return '#a78bfa';
      default: return '#c9d1d9';
    }
  };

  // Error state
  if (error) {
    return (
      <div style={styles.page}>
        <motion.div
          style={styles.errorCard}
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <AlertTriangle size={48} color="#ef4444" />
          <h2 style={{ marginTop: 16, fontSize: '1.4rem', fontWeight: 700 }}>Analysis Failed</h2>
          <p style={{ color: '#94a3b8', marginTop: 8, marginBottom: 24 }}>{error}</p>
          <Link to="/" style={styles.tryAgainBtn}>Try Another Repository</Link>
        </motion.div>
      </div>
    );
  }

  // Results state
  if (isComplete) {
    return <ResultsDashboard analysisId={id} />;
  }

  const progressColor = getProgressColor(displayProgress);

  return (
    <AnimatePresence>
      <motion.div
        style={styles.page}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        key="terminal-page"
      >
        <DotGrid />
        <LiquidBlobs />

        {/* Header from landing page to maintain consistency */}
        <header style={styles.header}>
          <div style={styles.logo}>
            <span style={styles.logoText}>CodeAutopsy</span>
            <span style={styles.badge}>BETA</span>
          </div>
        </header>

        <motion.div
          style={styles.terminal}
          initial={{ opacity: 0, y: 40, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          {/* Terminal title bar */}
          <div style={styles.titleBar}>
            <div style={styles.trafficLights}>
              <span style={{ ...styles.dot, background: '#ff5f57' }} />
              <span style={{ ...styles.dot, background: '#ffbd2e' }} />
              <span style={{ ...styles.dot, background: '#28c840' }} />
            </div>
            <span style={styles.titleText}>CodeAutopsy — Analysis Terminal</span>
            <div style={{ width: 60 }} />
          </div>

          {/* Terminal body */}
          <div style={styles.body}>
            {/* Scrollable output */}
            <div style={styles.outputArea}>
              {/* Welcome banner */}
              <div style={styles.banner}>
                <span style={{ color: '#6366f1', fontWeight: 700 }}>CodeAutopsy</span>
                <span style={{ color: '#475569' }}> v1.0.0 — AI-Powered Repository Analysis</span>
              </div>
              <div style={{ color: '#334155', marginBottom: 16, fontSize: '0.8rem' }}>
                ─────────────────────────────────────────────────
              </div>

              {/* Terminal lines */}
              {termLines.map((line, idx) => (
                <motion.div
                  key={line.id || idx}
                  style={{
                    ...styles.termLine,
                    color: getLineColor(line.color),
                    fontWeight: line.isCmd ? 600 : 400,
                    marginTop: line.isCmd ? 12 : 0,
                    paddingLeft: line.isCmd ? 0 : 16,
                  }}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  {line.text}
                  {/* Blinking cursor on last line if it's a command */}
                  {idx === termLines.length - 1 && (
                    <span style={styles.cursor} />
                  )}
                </motion.div>
              ))}

              <div ref={termEndRef} />
            </div>

            {/* Progress bar section */}
            <div style={styles.progressSection}>
              <div style={styles.progressHeader}>
                <span style={{ color: '#64748b', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                  PROGRESS
                </span>
                <span style={{
                  color: progressColor,
                  fontSize: '0.85rem',
                  fontWeight: 700,
                  fontFamily: 'monospace',
                  transition: 'color 0.5s ease',
                }}>
                  {displayProgress}%
                </span>
              </div>
              <div style={styles.progressTrack}>
                <motion.div
                  style={{
                    ...styles.progressFill,
                    width: `${displayProgress}%`,
                    background: `linear-gradient(90deg, #6366f1, ${progressColor})`,
                  }}
                  transition={{ duration: 0.4, ease: 'easeOut' }}
                />
                {/* Shimmer effect */}
                <div
                  style={{
                    ...styles.progressShimmer,
                    width: `${displayProgress}%`,
                  }}
                />
              </div>

              {/* Step indicators */}
              <div style={styles.stepRow}>
                {STEP_ORDER.filter(s => s !== 'queued').map(step => {
                  const ci = STEP_ORDER.indexOf(currentStep);
                  const si = STEP_ORDER.indexOf(step);
                  const isDone = si < ci || displayProgress === 100;
                  const isActive = si === ci && displayProgress < 100;
                  return (
                    <div key={step} style={styles.stepItem}>
                      <div style={{
                        ...styles.stepDot,
                        background: isDone ? '#10b981' : isActive ? '#6366f1' : '#1e293b',
                        border: isActive ? '2px solid #6366f1' : isDone ? '2px solid #10b981' : '2px solid #334155',
                        boxShadow: isActive ? '0 0 8px rgba(99,102,241,0.6)' : isDone ? '0 0 6px rgba(16,185,129,0.4)' : 'none',
                      }}>
                        {isDone && <span style={{ color: '#10b981', fontSize: '8px' }}>✓</span>}
                        {isActive && <span style={styles.activePulse} />}
                      </div>
                      <span style={{
                        ...styles.stepLabel,
                        color: isDone ? '#10b981' : isActive ? '#818cf8' : '#334155',
                      }}>
                        {STEP_LABELS[step]}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* Cancel hint */}
              <div style={styles.cancelHint}>
                <Link to="/" style={styles.cancelLink}>
                  <span style={{ color: '#ef4444' }}>^C</span> Cancel analysis
                </Link>
              </div>
            </div>
          </div>
        </motion.div>

        <style>{animStyles}</style>
      </motion.div>
    </AnimatePresence>
  );
}

const STEP_LABELS = {
  clone: 'Clone',
  file_tree: 'Index',
  static_analysis: 'Scan',
  scoring: 'AI Score',
  complete: 'Report',
};

// ─── Styles ────────────────────────────────────────────────────────────────

const styles = {
  page: {
    height: '100vh',
    width: '100vw',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#000',
    position: 'relative',
    overflow: 'hidden',
    padding: '24px',
  },
  header: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1.5rem 3rem',
    zIndex: 20,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  logoText: {
    fontSize: '1.25rem',
    fontWeight: 500,
    color: 'white',
    letterSpacing: '-0.5px',
  },
  badge: {
    fontSize: '0.7rem',
    padding: '0.15rem 0.5rem',
    borderRadius: '12px',
    border: '1px solid rgba(255, 255, 255, 0.3)',
    color: 'rgba(255, 255, 255, 0.8)',
    fontWeight: 500,
    letterSpacing: '0.5px',
  },
  terminal: {
    width: '100%',
    maxWidth: 760,
    background: '#0d1117',
    borderRadius: 12,
    border: '1px solid #21262d',
    boxShadow: '0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(99,102,241,0.08)',
    overflow: 'hidden',
    position: 'relative',
    zIndex: 10,
  },
  titleBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    background: '#161b22',
    borderBottom: '1px solid #21262d',
  },
  trafficLights: {
    display: 'flex',
    gap: 7,
    width: 60,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: '50%',
    display: 'inline-block',
  },
  titleText: {
    color: '#8b949e',
    fontSize: '0.78rem',
    fontFamily: 'monospace',
    letterSpacing: '0.02em',
  },
  body: {
    display: 'flex',
    flexDirection: 'column',
  },
  outputArea: {
    minHeight: 280,
    maxHeight: 340,
    overflowY: 'auto',
    padding: '20px 24px 12px',
    fontFamily: '"JetBrains Mono", "Fira Code", monospace',
    fontSize: '0.82rem',
    lineHeight: 1.7,
    scrollbarWidth: 'thin',
    scrollbarColor: '#21262d #0d1117',
  },
  banner: {
    fontSize: '0.88rem',
    marginBottom: 4,
    fontWeight: 500,
  },
  termLine: {
    display: 'flex',
    alignItems: 'baseline',
    gap: 4,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
  },
  cursor: {
    display: 'inline-block',
    width: 8,
    height: '1em',
    background: '#6366f1',
    marginLeft: 2,
    verticalAlign: 'text-bottom',
    animation: 'blink 1s step-end infinite',
  },
  progressSection: {
    padding: '16px 24px 20px',
    borderTop: '1px solid #21262d',
    background: '#0d1117',
  },
  progressHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressTrack: {
    height: 6,
    background: '#1c2128',
    borderRadius: 999,
    overflow: 'hidden',
    position: 'relative',
    marginBottom: 16,
  },
  progressFill: {
    height: '100%',
    borderRadius: 999,
    transition: 'width 0.4s ease-out',
    position: 'absolute',
    top: 0,
    left: 0,
  },
  progressShimmer: {
    position: 'absolute',
    top: 0,
    left: 0,
    height: '100%',
    background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.6s linear infinite',
    borderRadius: 999,
    pointerEvents: 'none',
  },
  stepRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 8,
    marginBottom: 14,
  },
  stepItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
    flex: 1,
  },
  stepDot: {
    width: 18,
    height: 18,
    borderRadius: '50%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.3s ease',
    position: 'relative',
  },
  activePulse: {
    position: 'absolute',
    inset: -4,
    borderRadius: '50%',
    border: '2px solid rgba(99,102,241,0.4)',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  stepLabel: {
    fontSize: '0.65rem',
    fontFamily: 'monospace',
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    transition: 'color 0.3s ease',
    textAlign: 'center',
  },
  cancelHint: {
    textAlign: 'center',
  },
  cancelLink: {
    color: '#334155',
    fontSize: '0.72rem',
    fontFamily: 'monospace',
    textDecoration: 'none',
    transition: 'color 0.2s',
  },
  errorCard: {
    background: '#0d1117',
    border: '1px solid #21262d',
    borderRadius: 16,
    padding: '48px 40px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    maxWidth: 420,
    width: '100%',
  },
  tryAgainBtn: {
    background: 'linear-gradient(135deg, #6366f1, #06b6d4)',
    color: 'white',
    padding: '12px 28px',
    borderRadius: 8,
    textDecoration: 'none',
    fontWeight: 600,
    fontSize: '0.9rem',
  },
};

const animStyles = `
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }
  @keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  @keyframes pulse {
    0%, 100% { opacity: 0.8; transform: scale(1); }
    50% { opacity: 0; transform: scale(1.6); }
  }
  .ap-cancel:hover { color: #64748b !important; }
  div[style*="outputArea"]::-webkit-scrollbar { width: 6px; }
  div[style*="outputArea"]::-webkit-scrollbar-track { background: #0d1117; }
  div[style*="outputArea"]::-webkit-scrollbar-thumb { background: #21262d; border-radius: 3px; }
`;
