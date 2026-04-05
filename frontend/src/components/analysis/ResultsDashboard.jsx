/**
 * Results Dashboard
 * Displays analysis results: health score, issues list, file tree, and severity breakdown.
 */

import { useState, useMemo, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft, Shield, FileCode, Bug, AlertTriangle,
  ChevronRight, ChevronDown, Filter, Search, Clock,
  Code2, GitBranch, Brain, Eye, Zap, Microscope, ExternalLink,
  AlertCircle, Info, CheckCircle2, Loader2, Download, X, Sparkles
} from 'lucide-react';
import useAnalysisStore from '../../lib/analysisStore';
import { downloadReport } from '../../lib/api';
import ArchaeologyPanel from '../archaeology/ArchaeologyPanel';
import AIPanel from './AIPanel';
import Navbar from '../ui/Navbar';
void motion;

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

export default function ResultsDashboard({ analysisId, errorBanner }) {
  const { 
    analysisResult,
    staticIssues,
    healthScore,
    repoName,
    languages,
    totalLines,
    fileTree,
    analysisStatus,
    aiSummary,
    aiSummaryStatus,
    aiSummaryError,
  } = useAnalysisStore();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const [severityFilter, setSeverityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [archaeologyTarget, setArchaeologyTarget] = useState(null);
  const [aiTarget, setAiTarget] = useState(null);
  const [editorLoading, setEditorLoading] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [exportingFormat, setExportingFormat] = useState(null);
  const navigate = useNavigate();
  const [errorBannerDismissed, setErrorBannerDismissed] = useState(false);
  
  // In case analysisResult is still hydrating from SSE, we gracefully fallback
  const finalHealthScore = healthScore ?? analysisResult?.health_score ?? 0;
  const rawIssues = useMemo(() => {
    if (Array.isArray(staticIssues) && staticIssues.length > 0) {
      return staticIssues;
    }
    if (Array.isArray(analysisResult?.issues) && analysisResult.issues.length > 0) {
      return analysisResult.issues;
    }
    return [];
  }, [staticIssues, analysisResult]);
  const issues = useMemo(
    () => [...rawIssues].sort(
      (a, b) => (SEVERITY_ORDER[a.severity] ?? 4) - (SEVERITY_ORDER[b.severity] ?? 4)
    ),
    [rawIssues]
  );
  const finalRepoName = repoName || analysisResult?.repo_name || 'Repository';
  const finalRepoUrl = analysisResult?.repo_url || sessionStorage.getItem('ca_repo_url') || '';
  const finalFileCount = fileTree?.length || analysisResult?.file_count || 0;
  const finalTotalLines = totalLines || analysisResult?.total_lines || 0;
  const finalLanguages = Object.keys(languages).length ? languages : (analysisResult?.languages || {});
  const finalTotalIssues = issues.length;

  const handleOpenEditor = async () => {
    setEditorLoading(true);
    // Small delay to show loading state before navigation
    await new Promise(r => setTimeout(r, 300));
    navigate(`/editor/${analysisId}`);
  };

  const handleExport = async (format) => {
    setExportingFormat(format);
    setExportDropdownOpen(false);
    try {
      await downloadReport(analysisId, format);
    } catch (error) {
      console.error('Failed to export report:', error);
      // Optional: Add toast notification here
    } finally {
      setExportingFormat(null);
    }
  };
  
  // Filter issues
  const filteredIssues = useMemo(() => {
    let filtered = issues || [];
    if (severityFilter !== 'all') {
      filtered = filtered.filter(i => i.severity === severityFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(i => 
        i.file_path.toLowerCase().includes(q) ||
        i.message.toLowerCase().includes(q) ||
        i.issue_type.toLowerCase().includes(q)
      );
    }
    return filtered;
  }, [issues, severityFilter, searchQuery]);
  
  // Severity counts
  const severityCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    (issues || []).forEach(i => {
      if (counts[i.severity] !== undefined) counts[i.severity]++;
    });
    return counts;
  }, [issues]);
  
  // Health score color
  const getScoreColor = (score) => {
    if (score >= 90) return 'var(--ca-success)';
    if (score >= 70) return 'var(--ca-primary-light)';
    if (score >= 50) return 'var(--ca-medium)';
    if (score >= 30) return 'var(--ca-high)';
    return 'var(--ca-critical)';
  };
  
  const getGrade = (score) => {
    if (score >= 90) return 'A';
    if (score >= 80) return 'B';
    if (score >= 70) return 'C';
    if (score >= 60) return 'D';
    return 'F';
  };
  
  // Severity icon
  const SeverityIcon = ({ severity }) => {
    const icons = {
      critical: <AlertCircle size={14} />,
      high: <AlertTriangle size={14} />,
      medium: <Info size={14} />,
      low: <CheckCircle2 size={14} />,
    };
    return icons[severity] || <Info size={14} />;
  };
  
  // Group issues by file for file tree view
  const issuesByFile = useMemo(() => {
    const grouped = {};
    (filteredIssues || []).forEach(i => {
      if (!grouped[i.file_path]) grouped[i.file_path] = [];
      grouped[i.file_path].push(i);
    });
    return grouped;
  }, [filteredIssues]);
  
  // Auto-expand all files if there are a reasonable number of them
  useEffect(() => {
    const filePaths = Object.keys(issuesByFile);
    if (filePaths.length > 0 && filePaths.length <= 15) {
      setExpandedFiles(new Set(filePaths));
    }
  }, [issuesByFile]);

  const toggleFile = (path) => {
    const newExpanded = new Set(expandedFiles);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedFiles(newExpanded);
  };
  
  return (
    <>
      <Navbar />
      <div className="results-page">
        <div className="container">
        {/* Header — flex layout for repo info on left and actions on right */}
        <div className="results-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', paddingBottom: '20px' }}>
          <div className="header-info">
            <Link to="/" className="back-link">
              <ArrowLeft size={16} />
              <span>New Analysis</span>
            </Link>
            <h1 className="repo-name" style={{ marginBottom: '4px' }}>{finalRepoName}</h1>
            {finalRepoUrl && (
              <a href={finalRepoUrl} target="_blank" rel="noopener noreferrer" className="repo-url" style={{ marginBottom: 0 }}>
                {finalRepoUrl}
              </a>
            )}
          </div>
          
          <div className="header-actions" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div style={{ position: 'relative' }}>
            <button 
              className="open-editor-btn"
              onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
              disabled={exportingFormat !== null}
              style={{ background: 'var(--ca-bg-elevated)', border: '1px solid var(--ca-border)', color: 'var(--ca-text)' }}
            >
              {exportingFormat ? (
                <>
                  <Loader2 size={14} className="editor-btn-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Download size={14} />
                  Export Report
                  <ChevronDown size={14} style={{ marginLeft: 4 }} />
                </>
              )}
            </button>
            {exportDropdownOpen && (
              <div style={{
                position: 'absolute', top: 'calc(100% + 8px)', right: 0,
                background: 'var(--ca-bg-elevated)', border: '1px solid var(--ca-border)',
                borderRadius: '8px', padding: '6px', zIndex: 50, display: 'flex', flexDirection: 'column', gap: '2px',
                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)', width: '160px'
              }}>
                <button 
                  onClick={() => handleExport('json')}
                  className="filter-btn"
                  style={{ justifyContent: 'flex-start', width: '100%', padding: '8px 12px', borderRadius: '6px' }}
                >
                  Raw JSON
                </button>
                <button 
                  onClick={() => handleExport('pdf')}
                  className="filter-btn"
                  style={{ justifyContent: 'flex-start', width: '100%', padding: '8px 12px', borderRadius: '6px' }}
                >
                  Summary PDF
                </button>
              </div>
            )}
            </div>

          <button 
            className="open-editor-btn"
            onClick={handleOpenEditor}
            disabled={editorLoading}
          >
            {editorLoading ? (
              <>
                <Loader2 size={14} className="editor-btn-spin" />
                Loading Editor...
              </>
            ) : (
              <>
                <Code2 size={14} />
                Open in Editor
              </>
            )}
          </button>
          </div>
        </div>
        
        {/* Error Banner — shown when analysis errored after Phase 1 */}
        {errorBanner && !errorBannerDismissed && (
          <motion.div
            className="error-banner"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 'var(--ca-radius)',
              padding: '14px 18px',
              marginBottom: '20px',
              borderLeft: '4px solid #ef4444',
            }}
          >
            <AlertTriangle size={18} color="#ef4444" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, color: '#ef4444', fontSize: '0.9rem', marginBottom: 2 }}>Analysis Error (Partial Results)</div>
              <div style={{ color: 'var(--ca-text-secondary)', fontSize: '0.82rem', lineHeight: 1.5 }}>{errorBanner}</div>
              <div style={{ color: 'var(--ca-text-muted)', fontSize: '0.75rem', marginTop: 4 }}>Static analysis completed — results below may be partial.</div>
            </div>
            <button
              onClick={() => setErrorBannerDismissed(true)}
              style={{ background: 'none', border: 'none', color: 'var(--ca-text-muted)', cursor: 'pointer', padding: 4, borderRadius: 6, flexShrink: 0 }}
            >
              <X size={16} />
            </button>
          </motion.div>
        )}

        {/* AI Summary Block — Premium Markdown Panel */}
        {(aiSummary || analysisStatus === 'ai_scanning' || aiSummaryError) && (
          <motion.div 
            className="ai-summary-panel"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            style={{ marginBottom: '32px' }}
          >
            {/* Panel Header */}
            <div className="ai-summary-header">
              <div className="ai-summary-header-left">
                <div className="ai-summary-icon">
                  <Brain size={18} />
                </div>
                <div>
                  <div className="ai-summary-title">AI Executive Summary</div>
                  <div className="ai-summary-subtitle">Powered by Ollama · Local LLM</div>
                </div>
              </div>
              <div className="ai-summary-status">
                {analysisStatus === 'ai_scanning' ? (
                  <>
                    <Loader2 size={14} className="spin" />
                    <span>Generating...</span>
                  </>
                ) : aiSummaryError ? (
                  <>
                    <AlertTriangle size={14} />
                    <span>{aiSummaryStatus === 'unavailable' ? 'Unavailable' : 'Warning'}</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={14} />
                    <span>Complete</span>
                  </>
                )}
              </div>
            </div>

            {/* Markdown Content Body */}
            <div className="ai-summary-body">
              {aiSummary ? (
                <ReactMarkdown 
                  remarkPlugins={[remarkGfm]}
                  components={{
                    h1: ({children}) => <h1 className="ai-md-h1">{children}</h1>,
                    h2: ({children}) => <h2 className="ai-md-h2">{children}</h2>,
                    h3: ({children}) => <h3 className="ai-md-h3">{children}</h3>,
                    p: ({children}) => <p className="ai-md-p">{children}</p>,
                    ul: ({children}) => <ul className="ai-md-ul">{children}</ul>,
                    ol: ({children}) => <ol className="ai-md-ol">{children}</ol>,
                    li: ({children}) => <li className="ai-md-li">{children}</li>,
                    code: ({inline, className, children, ...props}) => {
                      if (inline) {
                        return <code className="ai-md-inline-code" {...props}>{children}</code>;
                      }
                      return (
                        <div className="ai-md-code-block">
                          <pre><code className={className} {...props}>{children}</code></pre>
                        </div>
                      );
                    },
                    blockquote: ({children}) => <blockquote className="ai-md-blockquote">{children}</blockquote>,
                    strong: ({children}) => <strong className="ai-md-strong">{children}</strong>,
                    em: ({children}) => <em className="ai-md-em">{children}</em>,
                    hr: () => <hr className="ai-md-hr" />,
                    a: ({href, children}) => <a href={href} className="ai-md-link" target="_blank" rel="noopener noreferrer">{children}</a>,
                    table: ({children}) => <div className="ai-md-table-wrap"><table className="ai-md-table">{children}</table></div>,
                    th: ({children}) => <th className="ai-md-th">{children}</th>,
                    td: ({children}) => <td className="ai-md-td">{children}</td>,
                  }}
                >
                  {aiSummary}
                </ReactMarkdown>
              ) : aiSummaryError ? (
                <div className="ai-summary-warning">
                  <AlertTriangle size={18} />
                  <div>
                    <div className="ai-summary-warning-title">AI summary unavailable</div>
                    <div className="ai-summary-warning-text">{aiSummaryError}</div>
                  </div>
                </div>
              ) : (
                <div className="ai-summary-placeholder">
                  <div className="ai-summary-placeholder-text">Analyzing codebase patterns and compiling executive summary...</div>
                </div>
              )}
              {/* Blinking cursor while streaming */}
              {analysisStatus === 'ai_scanning' && (
                <span className="ai-stream-cursor" />
              )}
            </div>
          </motion.div>
        )}
        
        {/* Stats Cards */}
        <motion.div 
          className="stats-grid"
          initial="hidden"
          animate="visible"
          variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
        >
          {/* Health Score */}
          <motion.div className="stat-card health-score-card" variants={cardVariants}>
            <div className="health-score-circle" style={{ '--score-color': getScoreColor(finalHealthScore) }}>
              <svg viewBox="0 0 120 120" className="score-ring">
                <circle cx="60" cy="60" r="52" fill="none" stroke="var(--ca-border)" strokeWidth="8" />
                <circle 
                  cx="60" cy="60" r="52" fill="none" 
                  stroke={getScoreColor(finalHealthScore)} 
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(finalHealthScore / 100) * 327} 327`}
                  transform="rotate(-90 60 60)"
                  style={{ transition: 'stroke-dasharray 1s ease-out' }}
                />
              </svg>
              <div className="score-value">
                <span className="score-number">{finalHealthScore}</span>
                <span className="score-grade">{getGrade(finalHealthScore)}</span>
              </div>
            </div>
            <div className="stat-label">Health Score</div>
          </motion.div>
          
          {/* Issues Count */}
          <motion.div className="stat-card" variants={cardVariants}>
            <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #ef4444, #f97316)' }}>
              <Bug size={22} />
            </div>
            <div className="stat-value">{finalTotalIssues}</div>
            <div className="stat-label">Issues Found</div>
            <div className="severity-mini-bar">
              {Object.entries(severityCounts).map(([sev, count]) => (
                count > 0 && <span key={sev} className={`badge badge-${sev}`}>{count} {sev}</span>
              ))}
            </div>
          </motion.div>
          
          {/* Files Count */}
          <motion.div className="stat-card" variants={cardVariants}>
            <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
              <FileCode size={22} />
            </div>
            <div className="stat-value">{finalFileCount}</div>
            <div className="stat-label">Files Analyzed</div>
            <div className="stat-detail">{finalTotalLines?.toLocaleString()} lines of code</div>
          </motion.div>
          
          {/* Languages */}
          <motion.div className="stat-card" variants={cardVariants}>
            <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #06b6d4, #10b981)' }}>
              <Code2 size={22} />
            </div>
            <div className="stat-value">{Object.keys(finalLanguages || {}).length}</div>
            <div className="stat-label">Languages</div>
            <div className="stat-detail">
              {Object.entries(finalLanguages || {}).slice(0, 3).map(([lang, count]) => (
                <span key={lang} className="lang-chip">{lang}: {count}</span>
              ))}
            </div>
          </motion.div>
        </motion.div>
        
        {/* Issues Panel */}
        <motion.div 
          className="issues-panel card"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="issues-panel-header">
            <h2>
              <Shield size={20} />
              <span>Issues Found</span>
              <span className="issue-count-badge">{filteredIssues.length}</span>
            </h2>
            
            <div className="issues-filters">
              <div className="filter-search">
                <Search size={16} />
                <input 
                  type="text" 
                  placeholder="Search issues..." 
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              
              <div className="filter-severity">
                {['all', 'critical', 'high', 'medium', 'low'].map(sev => (
                  <button
                    key={sev}
                    className={`filter-btn ${severityFilter === sev ? 'active' : ''} ${sev !== 'all' ? `filter-${sev}` : ''}`}
                    onClick={() => setSeverityFilter(sev)}
                  >
                    {sev === 'all' ? 'All' : `${sev} (${severityCounts[sev] || 0})`}
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          <div className="issues-list">
            <AnimatePresence>
              {Object.entries(issuesByFile).map(([filePath, fileIssues]) => (
                <motion.div 
                  key={filePath} 
                  className="issue-file-group"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                >
                  <button 
                    className="file-group-header"
                    onClick={() => toggleFile(filePath)}
                  >
                    {expandedFiles.has(filePath) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <FileCode size={16} />
                    <span className="file-path">{filePath}</span>
                    <span className="file-issue-count">{fileIssues.length}</span>
                  </button>
                  
                  <AnimatePresence>
                    {expandedFiles.has(filePath) && (
                      <motion.div
                        className="file-issues"
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        {fileIssues.map((issue) => (
                          <div key={issue.id} className="issue-item">
                            <div className={`severity-dot ${issue.severity}`} />
                            <div className="issue-content">
                              <div className="issue-header-row">
                                <span className={`badge badge-${issue.severity}`}>
                                  <SeverityIcon severity={issue.severity} />
                                  {issue.severity}
                                </span>
                                <span className="issue-type">{issue.issue_type}</span>
                                <span className="issue-line">Line {issue.line_number}</span>
                              </div>
                              <p className="issue-message">{issue.message}</p>
                              {issue.code_snippet && (
                                <pre className="issue-snippet"><code>{issue.code_snippet}</code></pre>
                              )}
                              <div className="issue-actions">
                                <button
                                  className="trace-btn"
                                  onClick={() => setArchaeologyTarget({
                                    filePath: issue.file_path,
                                    lineNumber: issue.line_number,
                                    issueType: issue.issue_type,
                                  })}
                                >
                                  <Microscope size={13} />
                                  Trace Origin
                                </button>
                                <button
                                  className="ai-fix-btn"
                                  onClick={() => setAiTarget(issue)}
                                >
                                  <Brain size={13} />
                                  AI Fix
                                </button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </AnimatePresence>
            
            {filteredIssues.length === 0 && (
              <div className="no-issues">
                <CheckCircle2 size={32} color="var(--ca-success)" />
                <p>{searchQuery || severityFilter !== 'all' ? 'No issues match your filters' : 'No issues found! 🎉'}</p>
              </div>
            )}
          </div>
        </motion.div>
      </div>

      {/* Archaeology Panel Modal */}
      {archaeologyTarget && (
        <ArchaeologyPanel
          analysisId={analysisId}
          filePath={archaeologyTarget.filePath}
          lineNumber={archaeologyTarget.lineNumber}
          issueType={archaeologyTarget.issueType}
          onClose={() => setArchaeologyTarget(null)}
        />
      )}

      {/* AI Analysis Panel */}
      {aiTarget && (
        <AIPanel
          issue={aiTarget}
          onClose={() => setAiTarget(null)}
        />
      )}
      
      <style>{dashboardStyles}</style>
    </div>
    </>
  );
}

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
};

const dashboardStyles = `
  .results-page {
    min-height: 100vh;
    padding-top: 20px;
    padding-bottom: 48px;
  }
  
  .results-header {
    margin-bottom: 32px;
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: flex-end;
  }
  @media (max-width: 768px) {
    .results-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
    }
  }
  .open-editor-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 18px;
    border-radius: 8px;
    background: var(--ca-primary);
    color: white;
    border: none;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    font-family: var(--ca-font-sans);
    transition: all 0.15s;
  }
  .open-editor-btn:hover:not(:disabled) {
    background: var(--ca-primary-light);
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(99,102,241,0.3);
  }
  .open-editor-btn:disabled {
    opacity: 0.7;
    cursor: wait;
  }
  .editor-btn-spin {
    animation: editor-spin 1s linear infinite;
  }
  @keyframes editor-spin {
    to { transform: rotate(360deg); }
  }
  
  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--ca-text-secondary);
    text-decoration: none;
    font-size: 0.9rem;
    transition: color 0.2s;
  }
  
  .back-link:hover { color: var(--ca-primary-light); }
  
  .repo-name {
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 4px;
  }
  
  .repo-url {
    color: var(--ca-text-muted);
    font-size: 0.85rem;
    font-family: var(--ca-font-mono);
    text-decoration: none;
  }
  
  .repo-url:hover { color: var(--ca-primary-light); text-decoration: underline; }
  
  /* ─── Stats Grid ──────────────────────── */
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
  }
  
  .stat-card {
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: var(--ca-radius);
    padding: 24px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
  
  .stat-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
  }
  
  .stat-value {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
  
  .stat-label {
    color: var(--ca-text-secondary);
    font-size: 0.85rem;
    font-weight: 500;
  }
  
  .stat-detail {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    font-size: 0.8rem;
    color: var(--ca-text-muted);
  }
  
  .lang-chip {
    background: var(--ca-bg-secondary);
    padding: 2px 8px;
    border-radius: 4px;
    font-family: var(--ca-font-mono);
    font-size: 0.75rem;
  }
  
  .severity-mini-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    justify-content: center;
    margin-top: 4px;
  }
  
  .severity-mini-bar .badge {
    font-size: 0.65rem;
    padding: 2px 6px;
  }
  
  /* ─── Health Score Circle ─────────────── */
  
  .health-score-card {
    position: relative;
  }
  
  .health-score-circle {
    position: relative;
    width: 120px;
    height: 120px;
  }
  
  .score-ring {
    width: 100%;
    height: 100%;
  }
  
  .score-value {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  
  .score-number {
    font-size: 2rem;
    font-weight: 900;
    line-height: 1;
    color: var(--score-color);
  }
  
  .score-grade {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--ca-text-muted);
  }
  
  /* ─── Issues Panel ────────────────────── */
  
  .issues-panel {
    padding: 0;
    overflow: hidden;
  }
  
  .issues-panel-header {
    padding: 20px 24px;
    border-bottom: 1px solid var(--ca-border);
  }
  
  .issues-panel-header h2 {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 16px;
  }
  
  .issue-count-badge {
    background: var(--ca-bg-secondary);
    padding: 2px 10px;
    border-radius: 9999px;
    font-size: 0.8rem;
    font-weight: 600;
  }
  
  .issues-filters {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
  }
  
  .filter-search {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--ca-bg-secondary);
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    padding: 6px 12px;
    flex: 1;
    min-width: 200px;
    max-width: 300px;
  }
  
  .filter-search input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--ca-text);
    font-size: 0.85rem;
    width: 100%;
    font-family: var(--ca-font-sans);
  }
  
  .filter-search svg { color: var(--ca-text-muted); flex-shrink: 0; }
  
  .filter-severity {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  
  .filter-btn {
    padding: 4px 12px;
    border-radius: 6px;
    border: 1px solid var(--ca-border);
    background: var(--ca-bg-secondary);
    color: var(--ca-text-secondary);
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: capitalize;
    font-family: var(--ca-font-sans);
  }
  
  .filter-btn:hover { border-color: var(--ca-primary); }
  .filter-btn.active { background: var(--ca-primary); color: white; border-color: var(--ca-primary); }
  .filter-btn.filter-critical.active { background: var(--ca-critical); border-color: var(--ca-critical); }
  .filter-btn.filter-high.active { background: var(--ca-high); border-color: var(--ca-high); }
  .filter-btn.filter-medium.active { background: var(--ca-medium); border-color: var(--ca-medium); color: #000; }
  .filter-btn.filter-low.active { background: var(--ca-low); border-color: var(--ca-low); }
  
  /* ─── Issues List ─────────────────────── */
  
  .issues-list {
    max-height: 600px;
    overflow-y: auto;
  }
  
  .issue-file-group {
    border-bottom: 1px solid var(--ca-border);
  }
  
  .issue-file-group:last-child { border-bottom: none; }
  
  .file-group-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 12px 24px;
    background: transparent;
    border: none;
    color: var(--ca-text);
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    font-family: var(--ca-font-sans);
    text-align: left;
    transition: background 0.2s;
  }
  
  .file-group-header:hover { background: rgba(99, 102, 241, 0.05); }
  
  .file-path {
    flex: 1;
    font-family: var(--ca-font-mono);
    font-size: 0.85rem;
  }
  
  .file-issue-count {
    background: var(--ca-bg-secondary);
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    color: var(--ca-text-muted);
  }
  
  .file-issues {
    overflow: hidden;
  }
  
  .issue-item {
    display: flex;
    gap: 12px;
    padding: 12px 24px 12px 48px;
    border-top: 1px solid rgba(99, 102, 241, 0.05);
    transition: background 0.2s;
  }
  
  .issue-item:hover { background: rgba(99, 102, 241, 0.03); }
  
  .issue-content { flex: 1; min-width: 0; }
  
  .issue-header-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }
  
  .issue-type {
    font-family: var(--ca-font-mono);
    font-size: 0.8rem;
    color: var(--ca-text-secondary);
  }
  
  .issue-line {
    font-family: var(--ca-font-mono);
    font-size: 0.75rem;
    color: var(--ca-text-muted);
    margin-left: auto;
  }
  
  .issue-message {
    font-size: 0.85rem;
    color: var(--ca-text-secondary);
    margin-bottom: 8px;
    line-height: 1.5;
  }
  
  .issue-snippet {
    background: var(--ca-bg-secondary);
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 0.78rem;
    font-family: var(--ca-font-mono);
    overflow-x: auto;
    line-height: 1.6;
    color: var(--ca-text);
    border: 1px solid var(--ca-border);
  }
  
  .issue-actions {
    display: flex;
    gap: 6px;
    margin-top: 8px;
  }
  
  .trace-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 6px;
    background: rgba(99, 102, 241, 0.08);
    border: 1px solid rgba(99, 102, 241, 0.2);
    color: var(--ca-primary-light);
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    font-family: var(--ca-font-sans);
    transition: all 0.15s;
  }
  
  .trace-btn:hover {
    background: rgba(99, 102, 241, 0.15);
    border-color: var(--ca-primary);
  }
  
  .ai-fix-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 12px;
    border-radius: 6px;
    background: rgba(139, 92, 246, 0.08);
    border: 1px solid rgba(139, 92, 246, 0.2);
    color: #a78bfa;
    font-size: 0.78rem;
    font-weight: 600;
    cursor: pointer;
    font-family: var(--ca-font-sans);
    transition: all 0.15s;
  }
  
  .ai-fix-btn:hover {
    background: rgba(139, 92, 246, 0.15);
    border-color: #8b5cf6;
  }
  
  .no-issues {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 48px;
    color: var(--ca-text-secondary);
  }
  
  @media (max-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .issues-filters {
      flex-direction: column;
    }
    .filter-search {
      max-width: 100%;
    }
  }

  /* ─── Premium AI Summary Panel ──────────────── */

  .ai-summary-panel {
    background: linear-gradient(135deg, rgba(99,102,241,0.05) 0%, rgba(139,92,246,0.03) 100%);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: var(--ca-radius);
    overflow: hidden;
    box-shadow: 0 0 0 1px rgba(99,102,241,0.06) inset, 0 8px 32px rgba(0,0,0,0.25);
    backdrop-filter: blur(8px);
  }

  .ai-summary-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-bottom: 1px solid rgba(99,102,241,0.18);
    background: linear-gradient(90deg, rgba(99,102,241,0.10) 0%, rgba(139,92,246,0.06) 100%);
  }

  .ai-summary-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .ai-summary-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    box-shadow: 0 4px 12px rgba(99,102,241,0.35);
    flex-shrink: 0;
  }

  .ai-summary-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--ca-text);
    letter-spacing: -0.01em;
  }

  .ai-summary-subtitle {
    font-size: 0.72rem;
    color: var(--ca-text-muted);
    font-family: var(--ca-font-mono);
    margin-top: 1px;
  }

  .ai-summary-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--ca-primary-light);
    background: rgba(99,102,241,0.10);
    border: 1px solid rgba(99,102,241,0.2);
    border-radius: 20px;
    padding: 4px 12px;
  }

  .ai-summary-body {
    padding: 24px;
    position: relative;
  }

  .ai-summary-placeholder {
    padding: 20px 0;
  }

  .ai-summary-warning {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px 18px;
    background: rgba(245, 158, 11, 0.08);
    border: 1px solid rgba(245, 158, 11, 0.24);
    border-radius: 12px;
    color: var(--ca-text-secondary);
  }

  .ai-summary-warning-title {
    color: var(--ca-text);
    font-size: 0.9rem;
    font-weight: 700;
    margin-bottom: 4px;
  }

  .ai-summary-warning-text {
    color: var(--ca-text-secondary);
    font-size: 0.84rem;
    line-height: 1.6;
  }

  .ai-summary-placeholder-text {
    color: var(--ca-text-muted);
    font-size: 0.9rem;
    font-style: italic;
    animation: placeholder-pulse 2s ease-in-out infinite;
  }

  @keyframes placeholder-pulse {
    0%, 100% { opacity: 0.7; }
    50% { opacity: 1; }
  }

  .ai-stream-cursor {
    display: inline-block;
    width: 9px;
    height: 1.1em;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 2px;
    margin-left: 3px;
    vertical-align: text-bottom;
    animation: stream-blink 0.8s step-end infinite;
    box-shadow: 0 0 8px rgba(99,102,241,0.5);
  }

  @keyframes stream-blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
  }

  /* ─── Markdown Typography ─────────────── */

  .ai-md-h1 {
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--ca-text);
    margin: 0 0 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid rgba(99,102,241,0.2);
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #a5b4fc, #c4b5fd);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .ai-md-h2 {
    font-size: 1.15rem;
    font-weight: 700;
    color: #a5b4fc;
    margin: 24px 0 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .ai-md-h2::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 1em;
    background: linear-gradient(180deg, #6366f1, #8b5cf6);
    border-radius: 2px;
    flex-shrink: 0;
  }

  .ai-md-h3 {
    font-size: 1rem;
    font-weight: 700;
    color: var(--ca-text);
    margin: 18px 0 8px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.82rem;
    color: #94a3b8;
  }

  .ai-md-p {
    color: var(--ca-text-secondary);
    font-size: 0.92rem;
    line-height: 1.75;
    margin: 0 0 12px;
  }

  .ai-md-ul {
    list-style: none;
    margin: 0 0 14px;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .ai-md-ol {
    counter-reset: md-list;
    margin: 0 0 14px;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .ai-md-li {
    color: var(--ca-text-secondary);
    font-size: 0.9rem;
    line-height: 1.6;
    padding-left: 22px;
    position: relative;
  }

  .ai-md-ul > .ai-md-li::before {
    content: '▸';
    position: absolute;
    left: 0;
    color: #6366f1;
    font-size: 0.75rem;
    top: 3px;
  }

  .ai-md-ol > .ai-md-li {
    counter-increment: md-list;
  }

  .ai-md-ol > .ai-md-li::before {
    content: counter(md-list) '.';
    position: absolute;
    left: 0;
    color: #6366f1;
    font-size: 0.8rem;
    font-weight: 700;
    font-family: var(--ca-font-mono);
  }

  .ai-md-inline-code {
    background: rgba(99,102,241,0.12);
    border: 1px solid rgba(99,102,241,0.2);
    color: #a5b4fc;
    border-radius: 4px;
    padding: 1px 6px;
    font-family: var(--ca-font-mono);
    font-size: 0.82em;
  }

  .ai-md-code-block {
    background: #0d1117;
    border: 1px solid rgba(99,102,241,0.15);
    border-radius: 10px;
    padding: 16px 20px;
    margin: 12px 0;
    overflow-x: auto;
    position: relative;
  }

  .ai-md-code-block::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #06b6d4);
    border-radius: 10px 10px 0 0;
  }

  .ai-md-code-block pre {
    margin: 0;
  }

  .ai-md-code-block code {
    font-family: var(--ca-font-mono);
    font-size: 0.82rem;
    line-height: 1.75;
    color: #e2e8f0;
  }

  .ai-md-blockquote {
    border-left: 3px solid #6366f1;
    margin: 12px 0;
    padding: 10px 16px;
    background: rgba(99,102,241,0.06);
    border-radius: 0 8px 8px 0;
    color: var(--ca-text-secondary);
    font-style: italic;
    font-size: 0.9rem;
  }

  .ai-md-strong {
    font-weight: 700;
    color: var(--ca-text);
  }

  .ai-md-em {
    color: #c4b5fd;
    font-style: italic;
  }

  .ai-md-hr {
    border: none;
    border-top: 1px solid rgba(99,102,241,0.2);
    margin: 20px 0;
  }

  .ai-md-link {
    color: #818cf8;
    text-decoration: underline;
    text-underline-offset: 3px;
    transition: color 0.2s;
  }

  .ai-md-link:hover { color: #a5b4fc; }

  .ai-md-table-wrap {
    overflow-x: auto;
    margin: 12px 0;
    border-radius: 8px;
    border: 1px solid var(--ca-border);
  }

  .ai-md-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
  }

  .ai-md-th {
    background: rgba(99,102,241,0.08);
    color: var(--ca-primary-light);
    font-weight: 700;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid var(--ca-border);
  }

  .ai-md-td {
    color: var(--ca-text-secondary);
    padding: 9px 14px;
    border-bottom: 1px solid rgba(99,102,241,0.06);
  }

  .ai-md-table tr:last-child .ai-md-td { border-bottom: none; }
  .ai-md-table tr:hover .ai-md-td { background: rgba(99,102,241,0.03); }

  /* ─── AI Banner ───────────────────────── */
  .ai-progress-banner {
    position: sticky;
    top: 60px; /* Below Navbar */
    z-index: 40;
    margin: 0 auto 20px auto;
    max-width: 1200px;
    background: rgba(13, 17, 23, 0.85);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 12px;
    padding: 12px 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(99, 102, 241, 0.1) inset;
    animation: glow-pulse 3s infinite alternate;
  }
  
  @keyframes glow-pulse {
    0% { box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(99, 102, 241, 0.1) inset; }
    100% { box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(99, 102, 241, 0.3) inset, 0 0 15px rgba(99, 102, 241, 0.15); }
  }

  .ai-banner-content {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 12px;
  }

  .ai-banner-spinner {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 8px;
    background: rgba(99, 102, 241, 0.1);
    color: var(--ca-primary-light);
  }

  .spin {
    animation: simple-spin 1s linear infinite;
  }
  
  @keyframes simple-spin {
    to { transform: rotate(360deg); }
  }

  .ai-banner-text {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .ai-pulse-label {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--ca-text);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .ai-banner-detail {
    font-size: 0.8rem;
    color: var(--ca-primary-light);
    font-family: var(--ca-font-mono);
  }

  .ai-banner-bar-bg {
    width: 100%;
    height: 6px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    overflow: hidden;
  }

  .ai-banner-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #3b82f6);
    background-size: 200% 100%;
    border-radius: 4px;
    transition: width 0.4s ease-out;
    animation: bar-shimmer 2s infinite linear;
  }
  
  @keyframes bar-shimmer {
    0% { background-position: 100% 0; }
    100% { background-position: -100% 0; }
  }
`;
