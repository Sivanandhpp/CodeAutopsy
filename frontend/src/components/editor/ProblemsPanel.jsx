/**
 * Problems Panel — VS Code-style docked panel listing issues for the current file
 */

import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertCircle, AlertTriangle, Info, CheckCircle2,
  ChevronDown, ChevronUp, Bug, Filter, Microscope
} from 'lucide-react';

const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
const SEV_ICONS = {
  critical: <AlertCircle size={14} />,
  high: <AlertTriangle size={14} />,
  medium: <Info size={14} />,
  low: <CheckCircle2 size={14} />,
};

export default function ProblemsPanel({
  issues = [],
  filePath = '',
  onJumpToLine,
  onTraceOrigin,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [filter, setFilter] = useState('all');

  // Filter to current file's issues
  const fileIssues = useMemo(() => {
    let filtered = issues.filter(i => i.file_path === filePath);
    if (filter !== 'all') {
      filtered = filtered.filter(i => i.severity === filter);
    }
    return filtered.sort((a, b) =>
      (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9)
      || a.line_number - b.line_number
    );
  }, [issues, filePath, filter]);

  const sevCounts = useMemo(() => {
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    issues.filter(i => i.file_path === filePath).forEach(i => {
      if (counts[i.severity] !== undefined) counts[i.severity]++;
    });
    return counts;
  }, [issues, filePath]);

  const totalFileIssues = Object.values(sevCounts).reduce((a, b) => a + b, 0);

  return (
    <div className={`pp-wrap ${collapsed ? 'pp-collapsed' : ''}`}>
      {/* Header */}
      <button className="pp-header" onClick={() => setCollapsed(!collapsed)}>
        <div className="pp-header-left">
          <Bug size={14} />
          <span className="pp-title">Problems</span>
          {totalFileIssues > 0 && (
            <span className="pp-total-badge">{totalFileIssues}</span>
          )}
          {Object.entries(sevCounts).map(([sev, count]) =>
            count > 0 ? (
              <span key={sev} className={`pp-sev-pill pp-sev-${sev}`}>
                {SEV_ICONS[sev]} {count}
              </span>
            ) : null
          )}
        </div>
        {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {/* Body */}
      {!collapsed && (
        <div className="pp-body">
          {/* Mini filter */}
          {totalFileIssues > 4 && (
            <div className="pp-filters">
              {['all', 'critical', 'high', 'medium', 'low'].map(sev => (
                <button
                  key={sev}
                  className={`pp-filter-btn ${filter === sev ? 'active' : ''}`}
                  onClick={() => setFilter(sev)}
                >
                  {sev === 'all' ? 'All' : sev}
                </button>
              ))}
            </div>
          )}

          <div className="pp-list">
            {fileIssues.map((issue, idx) => (
              <div
                key={issue.id || idx}
                className="pp-item"
                onClick={() => onJumpToLine?.(issue.line_number)}
              >
                <span className={`pp-sev-icon pp-sev-${issue.severity}`}>
                  {SEV_ICONS[issue.severity]}
                </span>
                <span className="pp-message">{issue.message}</span>
                <span className="pp-type">{issue.issue_type}</span>
                <span className="pp-line">Ln {issue.line_number}</span>
                <button
                  className="pp-trace-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onTraceOrigin?.(issue);
                  }}
                  title="Trace bug origin"
                >
                  <Microscope size={12} />
                </button>
              </div>
            ))}
            {fileIssues.length === 0 && (
              <div className="pp-empty">
                {filePath
                  ? 'No issues in this file ✨'
                  : 'Select a file to see problems'}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .pp-wrap {
          background: var(--ca-bg-card);
          border-top: 1px solid var(--ca-border);
          display: flex;
          flex-direction: column;
          min-height: 36px;
          max-height: 240px;
        }
        .pp-collapsed {
          max-height: 36px;
        }
        .pp-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 6px 14px;
          background: transparent;
          border: none;
          color: var(--ca-text-secondary);
          cursor: pointer;
          font-family: var(--ca-font-sans);
          font-size: 0.8rem;
          border-bottom: 1px solid var(--ca-border);
        }
        .pp-header:hover { background: rgba(99,102,241,0.04); }
        .pp-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .pp-title { font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; font-size: 0.72rem; }
        .pp-total-badge {
          background: var(--ca-bg-secondary);
          padding: 1px 7px;
          border-radius: 8px;
          font-size: 0.7rem;
          font-weight: 600;
        }
        .pp-sev-pill {
          display: flex;
          align-items: center;
          gap: 3px;
          font-size: 0.68rem;
          font-weight: 600;
          padding: 1px 6px;
          border-radius: 4px;
        }
        .pp-sev-critical { color: var(--ca-critical); }
        .pp-sev-high { color: var(--ca-high); }
        .pp-sev-medium { color: var(--ca-medium); }
        .pp-sev-low { color: #06b6d4; }
        .pp-body { flex: 1; overflow-y: auto; }
        .pp-filters {
          display: flex;
          gap: 3px;
          padding: 4px 10px;
          border-bottom: 1px solid var(--ca-border);
        }
        .pp-filter-btn {
          padding: 2px 8px;
          border-radius: 4px;
          border: none;
          background: transparent;
          color: var(--ca-text-muted);
          font-size: 0.68rem;
          cursor: pointer;
          text-transform: capitalize;
          font-family: var(--ca-font-sans);
        }
        .pp-filter-btn.active {
          background: var(--ca-primary);
          color: white;
        }
        .pp-list { }
        .pp-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 5px 14px;
          cursor: pointer;
          font-size: 0.8rem;
          border-bottom: 1px solid rgba(99,102,241,0.04);
          transition: background 0.1s;
        }
        .pp-item:hover { background: rgba(99,102,241,0.06); }
        .pp-sev-icon { flex-shrink: 0; display: flex; }
        .pp-message {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: var(--ca-text-secondary);
        }
        .pp-type {
          font-family: var(--ca-font-mono);
          font-size: 0.7rem;
          color: var(--ca-text-muted);
          flex-shrink: 0;
        }
        .pp-line {
          font-family: var(--ca-font-mono);
          font-size: 0.7rem;
          color: var(--ca-text-muted);
          flex-shrink: 0;
          min-width: 44px;
          text-align: right;
        }
        .pp-trace-btn {
          background: none;
          border: none;
          color: var(--ca-text-muted);
          cursor: pointer;
          padding: 2px;
          border-radius: 4px;
          display: flex;
          transition: all 0.1s;
        }
        .pp-trace-btn:hover {
          color: var(--ca-primary-light);
          background: rgba(99,102,241,0.1);
        }
        .pp-empty {
          padding: 16px;
          text-align: center;
          color: var(--ca-text-muted);
          font-size: 0.8rem;
        }
      `}</style>
    </div>
  );
}
