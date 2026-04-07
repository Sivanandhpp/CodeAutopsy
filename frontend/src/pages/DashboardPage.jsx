/**
 * Dashboard Page
 * ==============
 * Post-login home screen showing all user projects with collaboration indicators,
 * health scores, quick actions, and a new analysis CTA.
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Plus, Search, BarChart3, GitBranch, Users, Clock, RefreshCw,
  ArrowRight, FolderOpen, Filter, Loader2, AlertCircle, Sparkles,
} from 'lucide-react';
import useAuthStore from '../lib/authStore';
import { getProjects, analyzeRepository } from '../lib/api';
import useAnalysisStore from '../lib/analysisStore';
import ProjectCard from '../components/dashboard/ProjectCard';
import CollaboratorModal from '../components/dashboard/CollaboratorModal';

export default function DashboardPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const { setAnalysisId, setAnalysisStatus } = useAnalysisStore();

  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [filterRole, setFilterRole] = useState('all');
  const [showNewAnalysis, setShowNewAnalysis] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [collabProject, setCollabProject] = useState(null);

  const fetchProjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getProjects();
      setProjects(data.projects || []);
      setError('');
    } catch (err) {
      setError('Failed to load projects');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleNewAnalysis = async (e) => {
    e.preventDefault();
    if (!newRepoUrl.trim() || analyzing) return;

    setAnalyzing(true);
    setError('');
    try {
      const data = await analyzeRepository(newRepoUrl.trim());
      setAnalysisId(data.analysis_id);
      setAnalysisStatus('analyzing');
      navigate(`/analysis/${data.analysis_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start analysis');
      setAnalyzing(false);
    }
  };

  // Filtering
  const filteredProjects = projects.filter((p) => {
    const matchSearch = !searchQuery ||
      p.repo_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.repo_url?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchRole = filterRole === 'all' || p.role === filterRole;
    return matchSearch && matchRole;
  });

  const stats = {
    total: projects.length,
    owned: projects.filter(p => p.role === 'owner').length,
    shared: projects.filter(p => p.role !== 'owner').length,
    healthy: projects.filter(p => (p.latest_analysis?.health_score ?? 0) >= 80).length,
  };

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  return (
    <div className="db-container">
      {/* Header */}
      <div className="db-header">
        <div className="db-header-text">
          <motion.h1 className="db-greeting"
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}>
            {greeting()}, <span className="db-greeting-name">{user?.username}</span>
          </motion.h1>
          <motion.p className="db-subtitle"
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, duration: 0.4 }}>
            Your code analysis dashboard — {projects.length} project{projects.length !== 1 ? 's' : ''} tracked
          </motion.p>
        </div>
        <motion.button className="db-new-btn" onClick={() => setShowNewAnalysis(!showNewAnalysis)}
          initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.15, duration: 0.3 }}
          whileHover={{ scale: 1.03, y: -1 }} whileTap={{ scale: 0.97 }}>
          <Plus size={17} strokeWidth={2.5} /> New Analysis
        </motion.button>
      </div>

      {/* New Analysis Expandable */}
      <AnimatePresence>
        {showNewAnalysis && (
          <motion.form className="db-new-form"
            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, height: 'auto', marginBottom: 24 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            onSubmit={handleNewAnalysis}>
            <div className="db-new-inner">
              <div className="db-new-icon">
                <GitBranch size={18} />
              </div>
              <input type="text" className="db-new-input"
                placeholder="Paste a GitHub repository URL..." value={newRepoUrl}
                onChange={(e) => setNewRepoUrl(e.target.value)} autoFocus />
              <button type="submit" className="db-analyze-btn" disabled={analyzing || !newRepoUrl.trim()}>
                {analyzing ? <Loader2 size={16} className="spin" /> : <><Sparkles size={15} /><span>Analyze</span><ArrowRight size={15} /></>}
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Stats Bar */}
      <div className="db-stats">
        {[
          { icon: FolderOpen, label: 'Total Projects', value: stats.total, gradient: 'linear-gradient(135deg, #6366f1, #818cf8)' },
          { icon: GitBranch, label: 'Owned', value: stats.owned, gradient: 'linear-gradient(135deg, #10b981, #34d399)' },
          { icon: Users, label: 'Shared With Me', value: stats.shared, gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)' },
          { icon: BarChart3, label: 'Healthy (80+)', value: stats.healthy, gradient: 'linear-gradient(135deg, #22c55e, #4ade80)' },
        ].map((s, i) => (
          <motion.div className="db-stat" key={s.label}
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.06, duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}>
            <div className="db-stat-icon" style={{ background: s.gradient }}>
              <s.icon size={16} />
            </div>
            <div className="db-stat-text">
              <span className="db-stat-value">{s.value}</span>
              <span className="db-stat-label">{s.label}</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Search & Filter */}
      <motion.div className="db-toolbar"
        initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.4 }}>
        <div className="db-search">
          <Search size={15} strokeWidth={2} />
          <input type="text" placeholder="Search projects..." value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)} />
          {searchQuery && (
            <button className="db-search-clear" onClick={() => setSearchQuery('')}>✕</button>
          )}
        </div>
        <div className="db-filters">
          {['all', 'owner', 'editor', 'viewer'].map((role) => (
            <button key={role} className={`db-filter ${filterRole === role ? 'active' : ''}`}
              onClick={() => setFilterRole(role)}>
              {role === 'all' ? 'All' : role.charAt(0).toUpperCase() + role.slice(1)}
            </button>
          ))}
        </div>
        <button className="db-refresh" onClick={fetchProjects} title="Refresh"
          disabled={loading}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} />
        </button>
      </motion.div>

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div className="db-error"
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}>
            <AlertCircle size={15} /> {error}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Projects Grid */}
      {loading ? (
        <div className="db-loading">
          <div className="db-loading-spinner">
            <Loader2 size={28} className="spin" />
          </div>
          <span>Loading your projects...</span>
        </div>
      ) : filteredProjects.length > 0 ? (
        <div className="db-grid">
          {filteredProjects.map((project, index) => (
            <ProjectCard key={project.id} project={project} index={index}
              onManageCollab={() => setCollabProject(project)}
              onRefresh={fetchProjects} />
          ))}
        </div>
      ) : (
        <motion.div className="db-empty"
          initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}>
          <div className="db-empty-glow" />
          <div className="db-empty-icon">🔬</div>
          <h3>No projects yet</h3>
          <p>Analyze your first GitHub repository to get started</p>
          <button className="db-new-btn" onClick={() => setShowNewAnalysis(true)}>
            <Plus size={17} strokeWidth={2.5} /> Start Your First Analysis
          </button>
        </motion.div>
      )}

      {/* Collaborator Modal */}
      {collabProject && (
        <CollaboratorModal project={collabProject}
          onClose={() => setCollabProject(null)} onUpdate={fetchProjects} />
      )}

      <style>{dashboardStyles}</style>
    </div>
  );
}

const dashboardStyles = `
  .db-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 28px 60px;
    min-height: calc(100vh - 64px);
  }

  /* ─── Header ─────────────────────────────── */
  .db-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 32px;
    gap: 16px;
  }
  .db-header-text {
    flex: 1;
    min-width: 0;
  }
  .db-greeting {
    font-size: 1.85rem;
    font-weight: 700;
    color: var(--ca-text);
    margin: 0;
    letter-spacing: -0.6px;
    line-height: 1.2;
  }
  .db-greeting-name {
    background: var(--ca-gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .db-subtitle {
    color: var(--ca-text-muted);
    font-size: 0.92rem;
    margin-top: 6px;
    letter-spacing: 0.01em;
  }

  /* ─── New Analysis Button ────────────────── */
  .db-new-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 11px 22px;
    background: var(--ca-gradient-primary);
    border: none;
    border-radius: 12px;
    color: white;
    font-weight: 600;
    font-size: 0.88rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.25);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .db-new-btn:hover {
    box-shadow: 0 8px 28px rgba(99, 102, 241, 0.4);
  }

  /* ─── New Analysis Form ──────────────────── */
  .db-new-form {
    overflow: hidden;
  }
  .db-new-inner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 16px;
    box-shadow: var(--ca-shadow-sm);
    transition: border-color 0.2s;
  }
  .db-new-inner:focus-within {
    border-color: var(--ca-primary);
    box-shadow: var(--ca-shadow-sm), 0 0 0 3px rgba(99, 102, 241, 0.08);
  }
  .db-new-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: rgba(99, 102, 241, 0.1);
    color: var(--ca-primary-light);
    flex-shrink: 0;
  }
  .db-new-input {
    flex: 1;
    padding: 10px 0;
    background: transparent;
    border: none;
    color: var(--ca-text);
    font-size: 0.95rem;
    font-family: inherit;
    outline: none;
  }
  .db-new-input::placeholder {
    color: var(--ca-text-muted);
  }
  .db-analyze-btn {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 10px 20px;
    background: var(--ca-gradient-primary);
    border: none;
    border-radius: 10px;
    color: white;
    font-weight: 600;
    font-size: 0.85rem;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    transition: all 0.2s;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
  }
  .db-analyze-btn:hover:not(:disabled) {
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
  }
  .db-analyze-btn:disabled { opacity: 0.45; cursor: not-allowed; }

  /* ─── Stats Bar ──────────────────────────── */
  .db-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 24px;
  }
  .db-stat {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 18px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 14px;
    transition: all 0.2s ease;
  }
  .db-stat:hover {
    border-color: var(--ca-glass-border);
    box-shadow: var(--ca-shadow-sm);
    transform: translateY(-1px);
  }
  .db-stat-icon {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }
  .db-stat-text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .db-stat-value {
    font-weight: 700;
    font-size: 1.25rem;
    color: var(--ca-text);
    line-height: 1.1;
    letter-spacing: -0.3px;
  }
  .db-stat-label {
    font-size: 0.76rem;
    color: var(--ca-text-muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* ─── Search & Filter Toolbar ────────────── */
  .db-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 24px;
  }
  .db-search {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 16px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 11px;
    flex: 1;
    min-width: 200px;
    color: var(--ca-text-muted);
    transition: all 0.2s;
  }
  .db-search:focus-within {
    border-color: var(--ca-primary);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08);
  }
  .db-search input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--ca-text);
    font-size: 0.88rem;
    font-family: inherit;
    width: 100%;
  }
  .db-search-clear {
    background: none;
    border: none;
    color: var(--ca-text-muted);
    cursor: pointer;
    font-size: 0.75rem;
    padding: 2px 6px;
    border-radius: 4px;
    transition: all 0.15s;
    line-height: 1;
  }
  .db-search-clear:hover {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }

  .db-filters { display: flex; gap: 3px; background: var(--ca-bg-card); border: 1px solid var(--ca-border); border-radius: 11px; padding: 3px; }
  .db-filter {
    padding: 6px 14px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: var(--ca-text-muted);
    font-size: 0.8rem;
    cursor: pointer;
    font-family: inherit;
    font-weight: 500;
    transition: all 0.2s;
  }
  .db-filter:hover:not(.active) {
    color: var(--ca-text);
    background: var(--ca-bg-secondary);
  }
  .db-filter.active {
    background: var(--ca-primary);
    color: white;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
  }
  .db-refresh {
    padding: 9px;
    border: 1px solid var(--ca-border);
    border-radius: 11px;
    background: var(--ca-bg-card);
    color: var(--ca-text-muted);
    cursor: pointer;
    display: flex;
    transition: all 0.2s;
  }
  .db-refresh:hover:not(:disabled) { border-color: var(--ca-primary); color: var(--ca-primary); }
  .db-refresh:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ─── Error ──────────────────────────────── */
  .db-error {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 13px 18px;
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.15);
    border-radius: 12px;
    color: #f87171;
    font-size: 0.88rem;
    margin-bottom: 20px;
    font-weight: 500;
  }

  /* ─── Projects Grid ──────────────────────── */
  .db-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 18px;
  }

  /* ─── Loading State ──────────────────────── */
  .db-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    padding: 80px 20px;
    color: var(--ca-text-muted);
    font-size: 0.9rem;
  }
  .db-loading-spinner {
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--ca-primary);
  }

  /* ─── Empty State ────────────────────────── */
  .db-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 80px 20px;
    text-align: center;
    position: relative;
  }
  .db-empty-glow {
    position: absolute;
    top: 40%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(99, 102, 241, 0.08) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
  }
  .db-empty-icon {
    font-size: 3.5rem;
    line-height: 1;
    position: relative;
  }
  .db-empty h3 {
    color: var(--ca-text);
    font-size: 1.2rem;
    margin: 0;
    font-weight: 600;
    letter-spacing: -0.3px;
  }
  .db-empty p {
    color: var(--ca-text-muted);
    font-size: 0.92rem;
    margin: 0 0 8px;
    max-width: 340px;
  }

  /* ─── Spin Animation ─────────────────────── */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.8s linear infinite; }

  /* ─── Responsive ─────────────────────────── */
  @media (max-width: 768px) {
    .db-container { padding: 24px 16px 60px; }
    .db-header { flex-direction: column; gap: 16px; }
    .db-greeting { font-size: 1.5rem; }
    .db-stats { grid-template-columns: repeat(2, 1fr); gap: 10px; }
    .db-toolbar { flex-wrap: wrap; }
    .db-search { min-width: 100%; order: -1; }
    .db-grid { grid-template-columns: 1fr; }
  }
  @media (max-width: 480px) {
    .db-stats { grid-template-columns: 1fr; }
    .db-filters { overflow-x: auto; }
    .db-stat-label { font-size: 0.72rem; }
  }
`;
