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
  ArrowRight, FolderOpen, Filter, Loader2, AlertCircle,
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

  return (
    <div className="db-container">
      {/* Header */}
      <div className="db-header">
        <div>
          <motion.h1 className="db-greeting"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            Welcome, {user?.username} 👋
          </motion.h1>
          <p className="db-subtitle">Your code analysis dashboard</p>
        </div>
        <motion.button className="db-new-btn" onClick={() => setShowNewAnalysis(!showNewAnalysis)}
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
          <Plus size={18} /> New Analysis
        </motion.button>
      </div>

      {/* New Analysis Expandable */}
      <AnimatePresence>
        {showNewAnalysis && (
          <motion.form className="db-new-form"
            initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }} onSubmit={handleNewAnalysis}>
            <div className="db-new-inner">
              <input type="text" className="db-new-input"
                placeholder="Paste a GitHub repository URL..." value={newRepoUrl}
                onChange={(e) => setNewRepoUrl(e.target.value)} autoFocus />
              <button type="submit" className="db-analyze-btn" disabled={analyzing || !newRepoUrl.trim()}>
                {analyzing ? <Loader2 size={16} className="spin" /> : <><span>Analyze</span><ArrowRight size={16} /></>}
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Stats Bar */}
      <div className="db-stats">
        {[
          { icon: FolderOpen, label: 'Total', value: stats.total, color: '#6366f1' },
          { icon: GitBranch, label: 'Owned', value: stats.owned, color: '#10b981' },
          { icon: Users, label: 'Shared', value: stats.shared, color: '#06b6d4' },
          { icon: BarChart3, label: 'Healthy', value: stats.healthy, color: '#22c55e' },
        ].map((s, i) => (
          <motion.div className="db-stat" key={s.label}
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}>
            <s.icon size={16} style={{ color: s.color }} />
            <span className="db-stat-value">{s.value}</span>
            <span className="db-stat-label">{s.label}</span>
          </motion.div>
        ))}
      </div>

      {/* Search & Filter */}
      <div className="db-toolbar">
        <div className="db-search">
          <Search size={16} />
          <input type="text" placeholder="Search projects..." value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
        <div className="db-filters">
          {['all', 'owner', 'editor', 'viewer'].map((role) => (
            <button key={role} className={`db-filter ${filterRole === role ? 'active' : ''}`}
              onClick={() => setFilterRole(role)}>
              {role === 'all' ? 'All' : role.charAt(0).toUpperCase() + role.slice(1)}
            </button>
          ))}
        </div>
        <button className="db-refresh" onClick={fetchProjects} title="Refresh">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="db-error"><AlertCircle size={16} /> {error}</div>
      )}

      {/* Projects Grid */}
      {loading ? (
        <div className="db-loading"><Loader2 size={24} className="spin" /><span>Loading projects...</span></div>
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
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="db-empty-icon">🔬</div>
          <h3>No projects yet</h3>
          <p>Analyze your first GitHub repository to get started</p>
          <button className="db-new-btn" onClick={() => setShowNewAnalysis(true)}>
            <Plus size={18} /> Start Your First Analysis
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
    padding: 32px 24px;
    min-height: calc(100vh - 64px);
  }

  .db-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
  }

  .db-greeting {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--ca-text);
    margin: 0;
    letter-spacing: -0.5px;
  }

  .db-subtitle {
    color: var(--ca-text-muted);
    font-size: 0.95rem;
    margin-top: 4px;
  }

  .db-new-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    border: none;
    border-radius: 12px;
    color: white;
    font-weight: 600;
    font-size: 0.9rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
  }
  .db-new-btn:hover { box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4); transform: translateY(-1px); }

  .db-new-form {
    overflow: hidden;
    margin-bottom: 20px;
  }
  .db-new-inner {
    display: flex;
    gap: 10px;
    padding: 16px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 16px;
  }
  .db-new-input {
    flex: 1;
    padding: 12px 16px;
    background: var(--ca-bg-secondary);
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    color: var(--ca-text);
    font-size: 0.95rem;
    font-family: inherit;
    outline: none;
  }
  .db-new-input:focus { border-color: var(--ca-primary); }
  .db-analyze-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 20px;
    background: var(--ca-primary);
    border: none;
    border-radius: 10px;
    color: white;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
  }
  .db-analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .db-stats {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .db-stat {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 12px;
    flex: 1;
    min-width: 120px;
  }
  .db-stat-value { font-weight: 700; font-size: 1.1rem; color: var(--ca-text); }
  .db-stat-label { font-size: 0.8rem; color: var(--ca-text-muted); }

  .db-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .db-search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 14px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    flex: 1;
    min-width: 200px;
    color: var(--ca-text-muted);
  }
  .db-search input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--ca-text);
    font-size: 0.9rem;
    font-family: inherit;
    width: 100%;
  }
  .db-filters { display: flex; gap: 4px; }
  .db-filter {
    padding: 6px 14px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: transparent;
    color: var(--ca-text-muted);
    font-size: 0.82rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.15s;
  }
  .db-filter.active {
    background: var(--ca-primary);
    border-color: var(--ca-primary);
    color: white;
  }
  .db-refresh {
    padding: 8px;
    border: 1px solid var(--ca-border);
    border-radius: 8px;
    background: transparent;
    color: var(--ca-text-muted);
    cursor: pointer;
    display: flex;
    transition: all 0.15s;
  }
  .db-refresh:hover { border-color: var(--ca-primary); color: var(--ca-primary); }

  .db-error {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    border-radius: 12px;
    color: #f87171;
    font-size: 0.9rem;
    margin-bottom: 16px;
  }

  .db-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
  }

  .db-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 60px 20px;
    color: var(--ca-text-muted);
  }

  .db-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 60px 20px;
    text-align: center;
  }
  .db-empty-icon { font-size: 3rem; }
  .db-empty h3 { color: var(--ca-text); font-size: 1.2rem; margin: 0; }
  .db-empty p { color: var(--ca-text-muted); font-size: 0.95rem; margin: 0 0 12px; }

  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.8s linear infinite; }

  @media (max-width: 640px) {
    .db-header { flex-direction: column; gap: 12px; }
    .db-grid { grid-template-columns: 1fr; }
    .db-stats { flex-direction: column; }
  }
`;
