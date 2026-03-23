/**
 * Results Dashboard
 * Displays analysis results: health score, issues list, file tree, and severity breakdown.
 */

import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Shield, FileCode, Bug, AlertTriangle,
  ChevronRight, ChevronDown, Filter, Search, Clock,
  Code2, GitBranch, Brain, Eye, Zap, Microscope, ExternalLink,
  AlertCircle, Info, CheckCircle2, Loader2
} from 'lucide-react';
import useAnalysisStore from '../../lib/analysisStore';
import ArchaeologyPanel from '../archaeology/ArchaeologyPanel';
import AIPanel from './AIPanel';

export default function ResultsDashboard({ analysisId }) {
  const { analysisResult } = useAnalysisStore();
  const [severityFilter, setSeverityFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [archaeologyTarget, setArchaeologyTarget] = useState(null);
  const [aiTarget, setAiTarget] = useState(null);
  const [editorLoading, setEditorLoading] = useState(false);
  const navigate = useNavigate();
  
  if (!analysisResult) return null;
  
  const { health_score, total_issues, file_count, total_lines, languages, issues, file_tree, repo_name, repo_url } = analysisResult;

  const handleOpenEditor = async () => {
    setEditorLoading(true);
    // Small delay to show loading state before navigation
    await new Promise(r => setTimeout(r, 300));
    navigate(`/editor/${analysisId}`);
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
    <div className="results-page">
      <div className="container">
        {/* Header — stacked vertically */}
        <div className="results-header">
          <Link to="/" className="back-link">
            <ArrowLeft size={16} />
            <span>New Analysis</span>
          </Link>
          <h1 className="repo-name">{repo_name || 'Repository'}</h1>
          <a href={repo_url} target="_blank" rel="noopener noreferrer" className="repo-url">
            {repo_url}
          </a>
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
        
        {/* Stats Cards */}
        <motion.div 
          className="stats-grid"
          initial="hidden"
          animate="visible"
          variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.08 } } }}
        >
          {/* Health Score */}
          <motion.div className="stat-card health-score-card" variants={cardVariants}>
            <div className="health-score-circle" style={{ '--score-color': getScoreColor(health_score) }}>
              <svg viewBox="0 0 120 120" className="score-ring">
                <circle cx="60" cy="60" r="52" fill="none" stroke="var(--ca-border)" strokeWidth="8" />
                <circle 
                  cx="60" cy="60" r="52" fill="none" 
                  stroke={getScoreColor(health_score)} 
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${(health_score / 100) * 327} 327`}
                  transform="rotate(-90 60 60)"
                  style={{ transition: 'stroke-dasharray 1s ease-out' }}
                />
              </svg>
              <div className="score-value">
                <span className="score-number">{health_score}</span>
                <span className="score-grade">{getGrade(health_score)}</span>
              </div>
            </div>
            <div className="stat-label">Health Score</div>
          </motion.div>
          
          {/* Issues Count */}
          <motion.div className="stat-card" variants={cardVariants}>
            <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #ef4444, #f97316)' }}>
              <Bug size={22} />
            </div>
            <div className="stat-value">{total_issues}</div>
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
            <div className="stat-value">{file_count}</div>
            <div className="stat-label">Files Analyzed</div>
            <div className="stat-detail">{total_lines?.toLocaleString()} lines of code</div>
          </motion.div>
          
          {/* Languages */}
          <motion.div className="stat-card" variants={cardVariants}>
            <div className="stat-icon" style={{ background: 'linear-gradient(135deg, #06b6d4, #10b981)' }}>
              <Code2 size={22} />
            </div>
            <div className="stat-value">{Object.keys(languages || {}).length}</div>
            <div className="stat-label">Languages</div>
            <div className="stat-detail">
              {Object.entries(languages || {}).slice(0, 3).map(([lang, count]) => (
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
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
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
    margin-top: 12px;
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
`;
