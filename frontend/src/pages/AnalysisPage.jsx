/**
 * Analysis Page
 * Shows real-time progress during analysis, then displays the results dashboard.
 */

import { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, AlertTriangle, CheckCircle2,
  Shield, FileCode, Activity, ExternalLink, Loader2
} from 'lucide-react';
import { getAnalysisResults } from '../lib/api';
import useAnalysisStore from '../lib/analysisStore';
import ResultsDashboard from '../components/analysis/ResultsDashboard';

export default function AnalysisPage() {
  const { id } = useParams();
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Starting analysis...');
  const [currentStep, setCurrentStep] = useState('queued');
  const [error, setError] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const eventSourceRef = useRef(null);
  
  const { analysisResult, setAnalysisResult, setAnalysisId } = useAnalysisStore();
  
  useEffect(() => {
    if (id) {
      setAnalysisId(id);
      startStreaming(id);
    }
    
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [id]);
  
  const startStreaming = (analysisId) => {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const eventSource = new EventSource(`${apiUrl}/api/analyze/stream/${analysisId}`);
    eventSourceRef.current = eventSource;
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setProgress(data.progress || 0);
        setStatusMessage(data.message || '');
        setCurrentStep(data.current_step || '');
        
        if (data.status === 'complete') {
          eventSource.close();
          fetchResults(analysisId);
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
        setIsComplete(true);
        setProgress(100);
        setStatusMessage('Analysis complete!');
      } else if (data.status === 'failed') {
        setError(data.error_message || 'Analysis failed');
      } else {
        setTimeout(() => fetchResults(analysisId), 3000);
      }
    } catch (err) {
      setError('Failed to fetch results. Please try again.');
    }
  };

  // ─── Circular Progress SVG ────────────────────
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  
  // Show progress view while analyzing
  if (!isComplete && !error) {
    return (
      <div className="ap-page">
        <div className="ap-center">
          <motion.div 
            className="ap-card"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            {/* Circular Progress */}
            <div className="ap-circle-wrap">
              <svg className="ap-circle-svg" viewBox="0 0 160 160">
                {/* Track */}
                <circle
                  cx="80" cy="80" r={radius}
                  fill="none"
                  stroke="var(--ca-border)"
                  strokeWidth="6"
                />
                {/* Animated gradient fill */}
                <circle
                  cx="80" cy="80" r={radius}
                  fill="none"
                  stroke="url(#progressGrad)"
                  strokeWidth="7"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  transform="rotate(-90 80 80)"
                  style={{ transition: 'stroke-dashoffset 0.6s ease-out' }}
                />
                {/* Glow filter */}
                <defs>
                  <linearGradient id="progressGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#6366f1" />
                    <stop offset="50%" stopColor="#8b5cf6" />
                    <stop offset="100%" stopColor="#06b6d4" />
                  </linearGradient>
                </defs>
              </svg>
              <div className="ap-circle-inner">
                <span className="ap-pct">{progress}%</span>
                <span className="ap-pct-label">progress</span>
              </div>
              {/* Spinning loader ring around circle */}
              <svg className="ap-spinner-ring" viewBox="0 0 160 160">
                <circle
                  cx="80" cy="80" r="78"
                  fill="none"
                  stroke="url(#spinGrad)"
                  strokeWidth="2"
                  strokeDasharray="40 200"
                  strokeLinecap="round"
                />
                <defs>
                  <linearGradient id="spinGrad">
                    <stop offset="0%" stopColor="#6366f1" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>

            <h2 className="ap-title">Analyzing Repository</h2>
            <p className="ap-msg">{statusMessage}</p>

            {/* Steps */}
            <div className="ap-steps">
              {progressSteps.map((step) => {
                const st = getStepStatus(currentStep, step.key);
                return (
                  <div key={step.key} className={`ap-step ap-step--${st}`}>
                    <div className="ap-step-icon">
                      {st === 'complete' ? (
                        <CheckCircle2 size={16} />
                      ) : st === 'active' ? (
                        <motion.div
                          className="ap-step-pulse"
                          animate={{ scale: [1, 1.25, 1] }}
                          transition={{ duration: 1.2, repeat: Infinity }}
                        >
                          {step.icon}
                        </motion.div>
                      ) : (
                        step.icon
                      )}
                    </div>
                    <span className="ap-step-label">{step.label}</span>
                    {st === 'active' && (
                      <Loader2 size={13} className="ap-step-spinner" />
                    )}
                    {st === 'complete' && (
                      <span className="ap-step-done">Done</span>
                    )}
                  </div>
                );
              })}
            </div>

            <Link to="/" className="ap-back">
              <ArrowLeft size={15} />
              Cancel
            </Link>
          </motion.div>
        </div>
        
        <style>{styles}</style>
      </div>
    );
  }
  
  // Show error
  if (error) {
    return (
      <div className="ap-page">
        <div className="ap-center">
          <motion.div 
            className="ap-card"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <AlertTriangle size={48} color="var(--ca-critical)" />
            <h2 className="ap-title" style={{ marginTop: 12 }}>Analysis Failed</h2>
            <p className="ap-msg">{error}</p>
            <Link to="/" className="btn-primary" style={{ textDecoration: 'none', marginTop: 8 }}>
              Try Another Repository
            </Link>
          </motion.div>
        </div>
        <style>{styles}</style>
      </div>
    );
  }
  
  return <ResultsDashboard analysisId={id} />;
}

// Step definitions
const progressSteps = [
  { key: 'clone', label: 'Cloning Repository', icon: <ExternalLink size={16} /> },
  { key: 'file_tree', label: 'Extracting Files', icon: <FileCode size={16} /> },
  { key: 'static_analysis', label: 'Security Analysis', icon: <Shield size={16} /> },
  { key: 'scoring', label: 'Calculating Score', icon: <Activity size={16} /> },
  { key: 'complete', label: 'Complete', icon: <CheckCircle2 size={16} /> },
];

function getStepStatus(currentStep, stepKey) {
  const order = ['clone', 'file_tree', 'static_analysis', 'scoring', 'complete'];
  const ci = order.indexOf(currentStep);
  const si = order.indexOf(stepKey);
  if (si < ci) return 'complete';
  if (si === ci) return 'active';
  return 'pending';
}

const styles = `
  .ap-page {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .ap-center {
    width: 100%;
    max-width: 480px;
  }

  .ap-card {
    background: var(--ca-glass-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--ca-glass-border);
    border-radius: 20px;
    padding: 40px 36px 28px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    box-shadow: 0 8px 40px rgba(0,0,0,0.25);
  }

  /* ─── Circular Progress ─────────────── */

  .ap-circle-wrap {
    position: relative;
    width: 160px;
    height: 160px;
    margin-bottom: 28px;
  }

  .ap-circle-svg {
    width: 100%;
    height: 100%;
  }

  .ap-circle-inner {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    pointer-events: none;
  }

  .ap-pct {
    font-size: 2.4rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, #6366f1, #06b6d4);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
  }

  .ap-pct-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ca-text-muted);
    margin-top: 2px;
    font-weight: 600;
  }

  .ap-spinner-ring {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    animation: spin 2.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* ─── Title & Message ───────────────── */

  .ap-title {
    font-size: 1.35rem;
    font-weight: 700;
    margin-bottom: 6px;
  }

  .ap-msg {
    color: var(--ca-text-secondary);
    font-size: 0.88rem;
    margin-bottom: 28px;
    min-height: 1.2em;
  }

  /* ─── Steps ─────────────────────────── */

  .ap-steps {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 20px;
  }

  .ap-step {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 14px;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 500;
    transition: all 0.3s ease;
  }

  .ap-step--complete {
    color: var(--ca-success);
  }

  .ap-step--active {
    color: var(--ca-primary-light);
    background: rgba(99, 102, 241, 0.1);
    font-weight: 600;
  }

  .ap-step--pending {
    color: var(--ca-text-muted);
    opacity: 0.5;
  }

  .ap-step-icon {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .ap-step-pulse {
    display: flex;
  }

  .ap-step-label {
    flex: 1;
    text-align: left;
  }

  .ap-step-spinner {
    animation: spin 1s linear infinite;
    opacity: 0.6;
  }

  .ap-step-done {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    opacity: 0.6;
  }

  /* ─── Back Link ─────────────────────── */

  .ap-back {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--ca-text-muted);
    text-decoration: none;
    font-size: 0.82rem;
    padding: 8px 16px;
    border-radius: 8px;
    transition: all 0.2s;
  }

  .ap-back:hover {
    color: var(--ca-text-secondary);
    background: var(--ca-bg-secondary);
  }

  @media (max-width: 500px) {
    .ap-card { padding: 28px 20px 20px; }
    .ap-circle-wrap { width: 130px; height: 130px; }
    .ap-pct { font-size: 2rem; }
  }
`;
