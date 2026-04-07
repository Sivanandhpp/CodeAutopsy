/**
 * ProjectCard — Individual Project Card for Dashboard
 * =====================================================
 * Shows repo info, health score, collaborators, and quick actions.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  GitBranch, BarChart3, FileCode, Clock, Users,
  ExternalLink, Play, Eye, Trash2, Loader2,
} from 'lucide-react';
import { deleteProject } from '../../lib/api';

function getScoreColor(score) {
  if (score >= 80) return '#10b981';
  if (score >= 60) return '#eab308';
  if (score >= 40) return '#f97316';
  return '#ef4444';
}

function getScoreGrade(score) {
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
}

function timeAgo(dateStr) {
  if (!dateStr) return 'Never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function ProjectCard({ project, index, onManageCollab, onRefresh }) {
  const navigate = useNavigate();
  const analysis = project.latest_analysis;
  const score = analysis?.health_score ?? null;
  const scoreColor = score !== null ? getScoreColor(score) : '#64748b';
  const isAnalyzing = analysis?.status === 'analyzing' || analysis?.status === 'cloning' || analysis?.status === 'queued';
  const [deleting, setDeleting] = useState(false);

  const handleViewResults = () => {
    if (analysis?.id) navigate(`/analysis/${analysis.id}`);
  };

  const handleOpenEditor = () => {
    if (analysis?.id) navigate(`/editor/${analysis.id}`);
  };

  const handleDelete = async () => {
    const isSure = window.confirm("Are you sure you want to delete this repository and all its analyses completely from the physical sandbox?");
    if (!isSure) return;
    setDeleting(true);
    try {
      await deleteProject(project.id);
      if (onRefresh) onRefresh();
    } catch (e) {
      alert("Failed to delete project: " + (e.response?.data?.detail || e.message));
      setDeleting(false);
    }
  };

  return (
    <motion.div className="pc-card"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35, ease: [0.25, 0.46, 0.45, 0.94] }}
      style={{ '--score-color': scoreColor }}
    >
      {/* Top accent line */}
      <div className="pc-accent" style={{ background: `linear-gradient(90deg, ${scoreColor}, ${scoreColor}88)` }} />

      {/* Header */}
      <div className="pc-header">
        <div className="pc-info">
          <div className="pc-repo-icon-wrap">
            <GitBranch size={15} />
          </div>
          <div className="pc-info-text">
            <h3 className="pc-name">{project.repo_name || 'Unnamed Project'}</h3>
            <span className="pc-role-badge" data-role={project.role}>
              {project.role}
            </span>
          </div>
        </div>

        {/* Health Score */}
        {score !== null && (
          <div className="pc-score" style={{ '--score-border': scoreColor }}>
            <svg className="pc-score-ring" viewBox="0 0 40 40">
              <circle cx="20" cy="20" r="16" fill="none" stroke="var(--ca-border)" strokeWidth="3" />
              <circle cx="20" cy="20" r="16" fill="none" stroke={scoreColor} strokeWidth="3"
                strokeDasharray={`${(score / 100) * 100.53} 100.53`}
                strokeLinecap="round"
                transform="rotate(-90 20 20)"
                style={{ transition: 'stroke-dasharray 0.6s ease' }} />
            </svg>
            <div className="pc-score-inner">
              <span className="pc-score-value" style={{ color: scoreColor }}>{score}</span>
              <span className="pc-score-grade" style={{ color: scoreColor }}>
                {getScoreGrade(score)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Stats Row */}
      {analysis && analysis.status === 'complete' && (
        <div className="pc-stats">
          <div className="pc-stat-item">
            <BarChart3 size={12} />
            <span>{analysis.total_issues ?? 0} issues</span>
          </div>
          <div className="pc-stat-item">
            <FileCode size={12} />
            <span>{analysis.file_count ?? 0} files</span>
          </div>
          <div className="pc-stat-item">
            <Clock size={12} />
            <span>{timeAgo(analysis.completed_at || analysis.created_at)}</span>
          </div>
        </div>
      )}

      {isAnalyzing && (
        <div className="pc-analyzing">
          <div className="pc-pulse" />
          <span>Analyzing...</span>
        </div>
      )}

      {!analysis && (
        <div className="pc-no-analysis">No analysis yet</div>
      )}

      {/* Collaborators */}
      <div className="pc-collab-row">
        <div className="pc-avatars">
          {(project.collaborators || []).slice(0, 4).map((c, i) => (
            <div key={c.user_id} className="pc-avatar" title={c.username}
              style={{ zIndex: 4 - i }}>
              {c.username.charAt(0).toUpperCase()}
            </div>
          ))}
          {(project.collaborators?.length || 0) > 4 && (
            <div className="pc-avatar pc-avatar-more">
              +{project.collaborators.length - 4}
            </div>
          )}
        </div>
        {project.role === 'owner' && (
          <button className="pc-manage-btn" onClick={onManageCollab} title="Manage team">
            <Users size={13} /> Manage
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="pc-actions">
        {analysis?.status === 'complete' && (
          <>
            <button className="pc-action pc-action-primary" onClick={handleViewResults}>
              <Eye size={13} /> Results
            </button>
            <button className="pc-action" onClick={handleOpenEditor}>
              <FileCode size={13} /> Editor
            </button>
          </>
        )}
        {isAnalyzing && analysis?.id && (
          <button className="pc-action pc-action-go" onClick={() => navigate(`/analysis/${analysis.id}`)}>
            <Play size={13} /> View Progress
          </button>
        )}
        
        {project.role === 'owner' && (
          <button 
            className="pc-action pc-action-danger" 
            onClick={handleDelete}
            disabled={deleting}
            title="Delete Repository and Sandbox"
          >
            {deleting ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
          </button>
        )}
        <a className="pc-action pc-action-ext" href={project.repo_url} target="_blank" rel="noreferrer" title="Open in GitHub">
          <ExternalLink size={13} />
        </a>
      </div>

      <style>{projectCardStyles}</style>
    </motion.div>
  );
}

const projectCardStyles = `
  .pc-card {
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 18px;
    padding: 22px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .pc-card:hover {
    border-color: color-mix(in srgb, var(--score-color, #6366f1) 25%, transparent);
    box-shadow:
      0 12px 40px rgba(0, 0, 0, 0.12),
      0 0 0 1px color-mix(in srgb, var(--score-color, #6366f1) 8%, transparent),
      0 0 40px color-mix(in srgb, var(--score-color, #6366f1) 5%, transparent);
    transform: translateY(-3px);
  }

  .pc-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
  }

  /* ─── Header ─────────────────────────── */
  .pc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  .pc-info {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    min-width: 0;
    flex: 1;
  }
  .pc-repo-icon-wrap {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: var(--ca-bg-elevated);
    border: 1px solid var(--ca-border);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--ca-text-muted);
    flex-shrink: 0;
    margin-top: 1px;
  }
  .pc-info-text {
    min-width: 0;
  }
  .pc-name {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--ca-text);
    margin: 0;
    word-break: break-word;
    line-height: 1.3;
    letter-spacing: -0.2px;
  }
  .pc-role-badge {
    display: inline-block;
    font-size: 0.65rem;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 5px;
  }
  .pc-role-badge[data-role="owner"] {
    background: rgba(99, 102, 241, 0.1);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.15);
  }
  .pc-role-badge[data-role="editor"] {
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.15);
  }
  .pc-role-badge[data-role="viewer"] {
    background: rgba(148, 163, 184, 0.1);
    color: #94a3b8;
    border: 1px solid rgba(148, 163, 184, 0.15);
  }

  /* ─── Score Ring ──────────────────────── */
  .pc-score {
    position: relative;
    width: 52px;
    height: 52px;
    flex-shrink: 0;
  }
  .pc-score-ring {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }
  .pc-score-inner {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }
  .pc-score-value {
    font-size: 0.95rem;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.3px;
  }
  .pc-score-grade {
    font-size: 0.6rem;
    font-weight: 700;
    line-height: 1;
    margin-top: 1px;
  }

  /* ─── Stats ──────────────────────────── */
  .pc-stats {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .pc-stat-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.78rem;
    color: var(--ca-text-muted);
  }

  .pc-analyzing {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    color: #818cf8;
    font-weight: 500;
  }
  .pc-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #818cf8;
    animation: pulse-animation 1.5s ease-in-out infinite;
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.4);
  }
  @keyframes pulse-animation {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(1.4); }
  }

  .pc-no-analysis {
    font-size: 0.82rem;
    color: var(--ca-text-muted);
    font-style: italic;
  }

  /* ─── Collaborators ──────────────────── */
  .pc-collab-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .pc-avatars {
    display: flex;
    margin-left: 2px;
  }
  .pc-avatar {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: var(--ca-gradient-primary);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.68rem;
    font-weight: 600;
    margin-left: -5px;
    border: 2px solid var(--ca-bg-card);
    position: relative;
    transition: transform 0.15s;
  }
  .pc-avatar:first-child { margin-left: 0; }
  .pc-avatar:hover { transform: translateY(-2px); z-index: 10 !important; }
  .pc-avatar-more {
    background: var(--ca-bg-elevated);
    color: var(--ca-text-muted);
    font-size: 0.62rem;
    border: 2px solid var(--ca-bg-card);
  }
  .pc-manage-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 10px;
    background: transparent;
    border: 1px solid var(--ca-border);
    border-radius: 7px;
    color: var(--ca-text-muted);
    font-size: 0.72rem;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .pc-manage-btn:hover { border-color: var(--ca-primary); color: var(--ca-primary); }

  /* ─── Actions ────────────────────────── */
  .pc-actions {
    display: flex;
    gap: 6px;
    margin-top: auto;
    padding-top: 2px;
  }
  .pc-action {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    background: var(--ca-bg-elevated);
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    color: var(--ca-text-secondary);
    font-size: 0.76rem;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
    text-decoration: none;
  }
  .pc-action:hover {
    border-color: var(--ca-primary);
    color: var(--ca-primary);
    background: rgba(99, 102, 241, 0.05);
  }
  .pc-action-primary {
    background: rgba(99, 102, 241, 0.08);
    border-color: rgba(99, 102, 241, 0.15);
    color: #818cf8;
  }
  .pc-action-primary:hover {
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.3);
    color: #6366f1;
  }
  .pc-action-go { border-color: rgba(99, 102, 241, 0.2); color: #818cf8; }
  .pc-action-danger { color: var(--ca-text-muted); border-color: transparent; padding: 6px 8px; }
  .pc-action-danger:hover { color: #ef4444; border-color: rgba(239,68,68,0.2); background: rgba(239,68,68,0.08); }
  .pc-action-ext { margin-left: auto; padding: 6px 8px; }

  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.8s linear infinite; }
`;
