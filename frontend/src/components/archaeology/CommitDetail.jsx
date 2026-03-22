/**
 * Commit Detail Card
 * Displays details of a single commit: hash, author, date, message, diff, stats.
 */

import { motion } from 'framer-motion';
import {
  GitCommit, User, Calendar, Plus, Minus, ArrowRight
} from 'lucide-react';

const CHANGE_BADGES = {
  introduction: { label: 'Introduction', color: '#f43f5e', bg: 'rgba(244,63,94,0.12)' },
  modification: { label: 'Modification', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  refactor: { label: 'Refactor', color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
};

export default function CommitDetail({ commit, isOrigin = false }) {
  if (!commit) return null;

  const badge = CHANGE_BADGES[commit.change_type] || CHANGE_BADGES.modification;

  // Relative time
  const relTime = getRelativeTime(commit.date);

  return (
    <motion.div 
      className="cd-card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      key={commit.commit_hash}
    >
      {/* Header */}
      <div className="cd-header">
        <div className="cd-badges">
          <span className="cd-badge-type" style={{ color: badge.color, background: badge.bg }}>
            {badge.label}
          </span>
          {isOrigin && (
            <span className="cd-badge-origin">🔬 Origin</span>
          )}
        </div>
        <span className="cd-hash">
          <GitCommit size={13} />
          {commit.commit_hash}
        </span>
      </div>

      {/* Info row */}
      <div className="cd-info">
        <span className="cd-author">
          <User size={13} />
          {commit.author}
        </span>
        <span className="cd-date">
          <Calendar size={13} />
          {relTime}
        </span>
        {(commit.insertions > 0 || commit.deletions > 0) && (
          <span className="cd-stats">
            <span className="cd-stat-add"><Plus size={12} />{commit.insertions || 0}</span>
            <span className="cd-stat-del"><Minus size={12} />{commit.deletions || 0}</span>
          </span>
        )}
      </div>

      {/* Commit message */}
      <p className="cd-message">{commit.message}</p>

      {/* Diff snippet */}
      {commit.diff && (
        <pre className="cd-diff">
          <code>{formatDiff(commit.diff)}</code>
        </pre>
      )}

      <style>{`
        .cd-card {
          background: var(--ca-bg-card);
          border: 1px solid var(--ca-border);
          border-radius: 12px;
          padding: 16px 20px;
        }
        .cd-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
          flex-wrap: wrap;
          gap: 8px;
        }
        .cd-badges {
          display: flex;
          gap: 6px;
        }
        .cd-badge-type {
          font-size: 0.72rem;
          font-weight: 600;
          padding: 3px 10px;
          border-radius: 6px;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }
        .cd-badge-origin {
          font-size: 0.72rem;
          font-weight: 600;
          padding: 3px 10px;
          border-radius: 6px;
          background: rgba(99,102,241,0.12);
          color: var(--ca-primary-light);
        }
        .cd-hash {
          display: flex;
          align-items: center;
          gap: 5px;
          font-family: var(--ca-font-mono);
          font-size: 0.8rem;
          color: var(--ca-text-muted);
        }
        .cd-info {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }
        .cd-author, .cd-date {
          display: flex;
          align-items: center;
          gap: 5px;
          font-size: 0.82rem;
          color: var(--ca-text-secondary);
        }
        .cd-stats {
          display: flex;
          gap: 8px;
          margin-left: auto;
        }
        .cd-stat-add {
          display: flex;
          align-items: center;
          gap: 2px;
          color: var(--ca-success);
          font-size: 0.8rem;
          font-weight: 600;
          font-family: var(--ca-font-mono);
        }
        .cd-stat-del {
          display: flex;
          align-items: center;
          gap: 2px;
          color: var(--ca-critical);
          font-size: 0.8rem;
          font-weight: 600;
          font-family: var(--ca-font-mono);
        }
        .cd-message {
          font-size: 0.88rem;
          color: var(--ca-text);
          margin-bottom: 10px;
          line-height: 1.5;
        }
        .cd-diff {
          background: var(--ca-bg-secondary);
          border: 1px solid var(--ca-border);
          border-radius: 8px;
          padding: 10px 14px;
          font-size: 0.75rem;
          font-family: var(--ca-font-mono);
          line-height: 1.7;
          overflow-x: auto;
          max-height: 180px;
          overflow-y: auto;
          white-space: pre;
        }
      `}</style>
    </motion.div>
  );
}

function getRelativeTime(dateStr) {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffS = Math.floor(diffMs / 1000);
    const diffM = Math.floor(diffS / 60);
    const diffH = Math.floor(diffM / 60);
    const diffD = Math.floor(diffH / 24);
    const diffW = Math.floor(diffD / 7);
    const diffMo = Math.floor(diffD / 30);
    const diffY = Math.floor(diffD / 365);

    if (diffY > 0) return `${diffY}y ago`;
    if (diffMo > 0) return `${diffMo}mo ago`;
    if (diffW > 0) return `${diffW}w ago`;
    if (diffD > 0) return `${diffD}d ago`;
    if (diffH > 0) return `${diffH}h ago`;
    if (diffM > 0) return `${diffM}m ago`;
    return 'just now';
  } catch {
    return dateStr;
  }
}

function formatDiff(diff) {
  if (!diff) return '';
  // Truncate to ~15 lines
  return diff.split('\n').slice(0, 15).join('\n');
}
