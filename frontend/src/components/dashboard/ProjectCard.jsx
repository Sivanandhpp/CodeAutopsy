/**
 * ProjectCard — Individual Project Card for Dashboard
 * =====================================================
 * Shows repo info, health score, collaborators, and quick actions.
 */

import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  GitBranch, BarChart3, FileCode, Clock, Users,
  ExternalLink, Play, Eye,
} from 'lucide-react';

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

  const handleViewResults = () => {
    if (analysis?.id) navigate(`/analysis/${analysis.id}`);
  };

  const handleOpenEditor = () => {
    if (analysis?.id) navigate(`/editor/${analysis.id}`);
  };

  return (
    <motion.div className="pc-card"
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      style={{ '--score-color': scoreColor }}
    >
      {/* Top accent line */}
      <div className="pc-accent" style={{ background: scoreColor }} />

      {/* Header */}
      <div className="pc-header">
        <div className="pc-info">
          <GitBranch size={16} className="pc-repo-icon" />
          <div>
            <h3 className="pc-name">{project.repo_name || 'Unnamed Project'}</h3>
            <span className="pc-role-badge" data-role={project.role}>
              {project.role}
            </span>
          </div>
        </div>

        {/* Health Score */}
        {score !== null && (
          <div className="pc-score" style={{ borderColor: scoreColor }}>
            <span className="pc-score-value" style={{ color: scoreColor }}>{score}</span>
            <span className="pc-score-grade" style={{ color: scoreColor }}>
              {getScoreGrade(score)}
            </span>
          </div>
        )}
      </div>

      {/* Stats Row */}
      {analysis && analysis.status === 'complete' && (
        <div className="pc-stats">
          <div className="pc-stat-item">
            <BarChart3 size={13} />
            <span>{analysis.total_issues ?? 0} issues</span>
          </div>
          <div className="pc-stat-item">
            <FileCode size={13} />
            <span>{analysis.file_count ?? 0} files</span>
          </div>
          <div className="pc-stat-item">
            <Clock size={13} />
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
            <Users size={14} /> Manage
          </button>
        )}
      </div>

      {/* Actions */}
      <div className="pc-actions">
        {analysis?.status === 'complete' && (
          <>
            <button className="pc-action" onClick={handleViewResults}>
              <Eye size={14} /> Results
            </button>
            <button className="pc-action" onClick={handleOpenEditor}>
              <FileCode size={14} /> Editor
            </button>
          </>
        )}
        {isAnalyzing && analysis?.id && (
          <button className="pc-action pc-action-go" onClick={() => navigate(`/analysis/${analysis.id}`)}>
            <Play size={14} /> View Progress
          </button>
        )}
        <a className="pc-action pc-action-ext" href={project.repo_url} target="_blank" rel="noreferrer">
          <ExternalLink size={14} />
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
    border-radius: 16px;
    padding: 20px;
    position: relative;
    overflow: hidden;
    transition: all 0.2s ease;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .pc-card:hover {
    border-color: color-mix(in srgb, var(--score-color, #6366f1) 30%, transparent);
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15), 0 0 0 1px color-mix(in srgb, var(--score-color, #6366f1) 10%, transparent);
    transform: translateY(-2px);
  }

  .pc-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
  }

  .pc-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .pc-info {
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .pc-repo-icon {
    color: var(--ca-text-muted);
    margin-top: 2px;
    flex-shrink: 0;
  }
  .pc-name {
    font-size: 1rem;
    font-weight: 600;
    color: var(--ca-text);
    margin: 0;
    word-break: break-all;
    line-height: 1.3;
  }
  .pc-role-badge {
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }
  .pc-role-badge[data-role="owner"] {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
  }
  .pc-role-badge[data-role="editor"] {
    background: rgba(16, 185, 129, 0.15);
    color: #34d399;
  }
  .pc-role-badge[data-role="viewer"] {
    background: rgba(148, 163, 184, 0.15);
    color: #94a3b8;
  }

  .pc-score {
    border: 2px solid;
    border-radius: 12px;
    padding: 6px 10px;
    text-align: center;
    min-width: 50px;
    flex-shrink: 0;
  }
  .pc-score-value { font-size: 1.1rem; font-weight: 700; display: block; line-height: 1.1; }
  .pc-score-grade { font-size: 0.7rem; font-weight: 600; }

  .pc-stats {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .pc-stat-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.8rem;
    color: var(--ca-text-muted);
  }

  .pc-analyzing {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: #818cf8;
  }
  .pc-pulse {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #818cf8;
    animation: pulse-animation 1.5s ease-in-out infinite;
  }
  @keyframes pulse-animation {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(1.3); }
  }

  .pc-no-analysis {
    font-size: 0.85rem;
    color: var(--ca-text-muted);
    font-style: italic;
  }

  .pc-collab-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .pc-avatars {
    display: flex;
    margin-left: 4px;
  }
  .pc-avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 600;
    margin-left: -6px;
    border: 2px solid var(--ca-bg-card);
    position: relative;
  }
  .pc-avatar:first-child { margin-left: 0; }
  .pc-avatar-more { background: var(--ca-bg-elevated); color: var(--ca-text-muted); font-size: 0.65rem; }

  .pc-manage-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: transparent;
    border: 1px solid var(--ca-border);
    border-radius: 6px;
    color: var(--ca-text-muted);
    font-size: 0.75rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .pc-manage-btn:hover { border-color: var(--ca-primary); color: var(--ca-primary); }

  .pc-actions {
    display: flex;
    gap: 6px;
    margin-top: auto;
  }
  .pc-action {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    background: var(--ca-bg-elevated);
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    color: var(--ca-text-secondary);
    font-size: 0.78rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
    text-decoration: none;
  }
  .pc-action:hover { border-color: var(--ca-primary); color: var(--ca-primary); }
  .pc-action-go { border-color: #6366f1; color: #818cf8; }
  .pc-action-ext { margin-left: auto; padding: 6px 8px; }
`;
