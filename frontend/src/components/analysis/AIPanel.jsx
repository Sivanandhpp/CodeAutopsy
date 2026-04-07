/**
 * AI Panel — Modal overlay showing Groq AI analysis results
 * Triggered from issue items in ResultsDashboard or ProblemsPanel
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Brain, Loader2, Lightbulb, Wrench, Code2,
  Gauge, ListChecks, AlertTriangle, Sparkles
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMemo } from 'react';
import useAnalysisStore from '../../lib/analysisStore';
import { analyzeWithAI } from '../../lib/api';

export default function AIPanel({ issue, onClose }) {
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const analysisResult = useAnalysisStore(state => state.analysisResult);
  const aiModelMeta = useMemo(() => {
    let findings = analysisResult?.ollama_findings || [];
    if (typeof findings === 'string') {
      try { findings = JSON.parse(findings); } catch(e) { findings = []; }
    }
    const meta = findings.find(f => f.type === 'ai_meta');
    return meta?.model_info || 'Local LLM';
  }, [analysisResult]);

  useEffect(() => {
    if (issue) {
      fetchAIAnalysis();
    }
  }, [issue]);

  async function fetchAIAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const data = await analyzeWithAI(
        issue.code_snippet || '',
        issue.defect_family || 'unknown',
        issue.language || detectLang(issue.file_path),
      );
      setResult(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'AI analysis failed');
    } finally {
      setLoading(false);
    }
  }

  function detectLang(filePath) {
    if (!filePath) return 'plaintext';
    const ext = filePath.split('.').pop()?.toLowerCase();
    const map = {
      py: 'python', js: 'javascript', ts: 'typescript', jsx: 'javascript',
      tsx: 'typescript', java: 'java', go: 'go', rs: 'rust', rb: 'ruby',
      php: 'php', c: 'c', cpp: 'c++', cs: 'csharp', html: 'html',
      css: 'css', sql: 'sql', sh: 'shell', yml: 'yaml', yaml: 'yaml',
    };
    return map[ext] || 'plaintext';
  }

  const confidenceColor = (c) => {
    if (c >= 0.8) return '#10b981';
    if (c >= 0.5) return '#eab308';
    return '#ef4444';
  };

  const confidenceLabel = (c) => {
    if (c >= 0.8) return 'High';
    if (c >= 0.5) return 'Medium';
    return 'Low';
  };

  return (
    <AnimatePresence>
      <motion.div
        className="ai-overlay"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className="ai-modal"
          initial={{ opacity: 0, y: 40, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 40, scale: 0.96 }}
          transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="ai-header">
            <div className="ai-header-left">
              <div className="ai-header-icon">
                <Brain size={20} />
              </div>
              <div>
                <h2>AI Analysis</h2>
                <span className="ai-subtitle">
                  {(issue.defect_family || 'unknown')} · {issue.file_path?.split('/').pop() || 'file'}
                  {issue.line_number ? ` · Line ${issue.line_number}` : ''}
                </span>
              </div>
            </div>
            <button className="ai-close" onClick={onClose}>
              <X size={18} />
            </button>
          </div>

          {/* Body */}
          <div className="ai-body">
            {loading && (
              <div className="ai-loading">
                <Loader2 size={28} className="ai-spin" />
                <p>Analyzing with {aiModelMeta}...</p>
                <span className="ai-loading-sub">Private &amp; Fast</span>
              </div>
            )}

            {error && (
              <div className="ai-error">
                <AlertTriangle size={24} />
                <p>{error}</p>
                <button className="ai-retry" onClick={fetchAIAnalysis}>Try Again</button>
              </div>
            )}

            {!loading && !error && result && (
              <>
                {/* Confidence Bar */}
                <div className="ai-confidence">
                  <div className="ai-conf-header">
                    <Gauge size={16} />
                    <span>Confidence</span>
                    <span
                      className="ai-conf-value"
                      style={{ color: confidenceColor(result.confidence) }}
                    >
                      {Math.round(result.confidence * 100)}% — {confidenceLabel(result.confidence)}
                    </span>
                  </div>
                  <div className="ai-conf-bar">
                    <motion.div
                      className="ai-conf-fill"
                      initial={{ width: 0 }}
                      animate={{ width: `${result.confidence * 100}%` }}
                      transition={{ duration: 0.8, ease: 'easeOut' }}
                      style={{ background: confidenceColor(result.confidence) }}
                    />
                  </div>
                  {result.cached && (
                    <span className="ai-cached-badge">⚡ Cached result</span>
                  )}
                </div>

                {/* Root Cause */}
                <div className="ai-section">
                  <div className="ai-section-header">
                    <Lightbulb size={16} />
                    <h3>Root Cause</h3>
                  </div>
                  <div className="ai-section-text ai-md-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.root_cause}</ReactMarkdown>
                  </div>
                </div>

                {/* Fix Strategy */}
                <div className="ai-section">
                  <div className="ai-section-header">
                    <Wrench size={16} />
                    <h3>Fix Strategy</h3>
                  </div>
                  <div className="ai-section-text ai-md-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.fix_strategy}</ReactMarkdown>
                  </div>
                </div>

                {/* Code Patch */}
                <div className="ai-section">
                  <div className="ai-section-header">
                    <Code2 size={16} />
                    <h3>Suggested Fix</h3>
                  </div>
                  <pre className="ai-code-block">
                    <code>{result.code_patch}</code>
                  </pre>
                </div>

                {/* Reasoning */}
                {result.reasoning && result.reasoning.length > 0 && (
                  <div className="ai-section">
                    <div className="ai-section-header">
                      <ListChecks size={16} />
                      <h3>Reasoning</h3>
                    </div>
                    <ol className="ai-reasoning">
                      {result.reasoning.map((step, i) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ol>
                  </div>
                )}

                {/* Footer */}
                <div className="ai-footer">
                  <Sparkles size={12} />
                  <span>Generated by {aiModelMeta}</span>
                </div>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>

      <style>{aiPanelStyles}</style>
    </AnimatePresence>
  );
}

const aiPanelStyles = `
  .ai-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }

  .ai-modal {
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 16px;
    width: 100%;
    max-width: 640px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--ca-shadow-lg);
    overflow: hidden;
  }

  .ai-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    border-bottom: 1px solid var(--ca-border);
    flex-shrink: 0;
  }
  .ai-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .ai-header-icon {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
  }
  .ai-header h2 {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0;
  }
  .ai-subtitle {
    font-size: 0.78rem;
    color: var(--ca-text-muted);
    font-family: var(--ca-font-mono);
  }
  .ai-close {
    background: none;
    border: none;
    color: var(--ca-text-muted);
    cursor: pointer;
    padding: 6px;
    border-radius: 8px;
    display: flex;
    transition: all 0.15s;
  }
  .ai-close:hover {
    background: var(--ca-bg-secondary);
    color: var(--ca-text);
  }

  .ai-body {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
  }

  /* Loading */
  .ai-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 48px 24px;
    color: var(--ca-text-secondary);
  }
  .ai-loading p { font-weight: 600; font-size: 0.95rem; }
  .ai-loading-sub { font-size: 0.75rem; color: var(--ca-text-muted); }
  .ai-spin {
    animation: ai-spin-anim 1s linear infinite;
    color: var(--ca-primary-light);
  }
  @keyframes ai-spin-anim {
    to { transform: rotate(360deg); }
  }

  /* Error */
  .ai-error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 48px 24px;
    color: var(--ca-critical);
    text-align: center;
  }
  .ai-error p { color: var(--ca-text-secondary); font-size: 0.9rem; }
  .ai-retry {
    background: var(--ca-primary);
    color: white;
    border: none;
    padding: 6px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.82rem;
    cursor: pointer;
    font-family: var(--ca-font-sans);
  }

  /* Confidence */
  .ai-confidence {
    margin-bottom: 20px;
    padding: 14px 16px;
    background: var(--ca-bg-secondary);
    border-radius: 10px;
    border: 1px solid var(--ca-border);
  }
  .ai-conf-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--ca-text-secondary);
    margin-bottom: 8px;
  }
  .ai-conf-value {
    font-weight: 700;
    margin-left: auto;
    font-size: 0.85rem;
  }
  .ai-conf-bar {
    height: 6px;
    background: var(--ca-border);
    border-radius: 3px;
    overflow: hidden;
  }
  .ai-conf-fill {
    height: 100%;
    border-radius: 3px;
  }
  .ai-cached-badge {
    display: inline-block;
    margin-top: 6px;
    font-size: 0.7rem;
    color: var(--ca-text-muted);
  }

  /* Sections */
  .ai-section {
    margin-bottom: 18px;
  }
  .ai-section-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    color: var(--ca-primary-light);
  }
  .ai-section-header h3 {
    font-size: 0.88rem;
    font-weight: 700;
    margin: 0;
    color: var(--ca-text);
  }
  .ai-section-text {
    color: var(--ca-text-secondary);
    font-size: 0.85rem;
    line-height: 1.6;
    margin: 0;
  }

  /* Code block */
  .ai-code-block {
    background: var(--ca-bg);
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    padding: 14px 16px;
    font-family: var(--ca-font-mono);
    font-size: 0.8rem;
    line-height: 1.7;
    overflow-x: auto;
    color: var(--ca-text);
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  /* Reasoning */
  .ai-reasoning {
    margin: 0;
    padding-left: 20px;
    color: var(--ca-text-secondary);
    font-size: 0.82rem;
    line-height: 1.7;
  }
  .ai-reasoning li {
    margin-bottom: 4px;
  }

  /* Footer */
  .ai-footer {
    display: flex;
    align-items: center;
    gap: 6px;
    justify-content: center;
    padding-top: 16px;
    margin-top: 8px;
    border-top: 1px solid var(--ca-border);
    font-size: 0.7rem;
    color: var(--ca-text-muted);
  }

  @media (max-width: 640px) {
    .ai-modal { max-height: 90vh; border-radius: 12px; }
    .ai-body { padding: 16px; }
  }

  /* Markdown rendered inside AIPanel sections */
  .ai-md-content p {
    color: var(--ca-text-secondary);
    font-size: 0.85rem;
    line-height: 1.65;
    margin: 0 0 8px;
  }
  .ai-md-content p:last-child { margin-bottom: 0; }
  .ai-md-content ul, .ai-md-content ol {
    margin: 6px 0 8px;
    padding-left: 18px;
    color: var(--ca-text-secondary);
    font-size: 0.85rem;
    line-height: 1.6;
  }
  .ai-md-content li { margin-bottom: 4px; }
  .ai-md-content code {
    background: rgba(99,102,241,0.12);
    border: 1px solid rgba(99,102,241,0.2);
    color: #a5b4fc;
    border-radius: 4px;
    padding: 1px 5px;
    font-family: var(--ca-font-mono);
    font-size: 0.8em;
  }
  .ai-md-content strong { font-weight: 700; color: var(--ca-text); }
  .ai-md-content em { color: #c4b5fd; font-style: italic; }
`;

