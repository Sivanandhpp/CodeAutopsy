import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldAlert, Users as UsersIcon, Database, HardDrive, 
  Trash2, RefreshCw, AlertTriangle, AlertCircle, FileJson, 
  Upload, Terminal, CheckCircle, Activity, TrendingUp,
  ChevronRight, Search, MoreHorizontal
} from 'lucide-react';
import useAuthStore from '../lib/authStore';
import { 
  getAdminStats, getAdminUsers, adminDeleteUser, 
  getAdminRepos, adminDeleteRepo, adminDeleteAllRepos, 
  getAdminAuditLogs, getAdminRules, adminBulkImportRulesJson,
  adminBulkImportRulesCsv, adminToggleRule, adminDeleteRule
} from '../lib/api';
import ConfirmModal from '../components/ui/ConfirmModal';

export default function AdminPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Data
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [repos, setRepos] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [rules, setRules] = useState([]);

  // Modals
  const [confirmModal, setConfirmModal] = useState({ isOpen: false, data: null });

  // Rules Import
  const fileInputRef = useRef(null);
  const [importLoading, setImportLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      if (activeTab === 'overview') {
        const [statsData, logsData] = await Promise.all([getAdminStats(), getAdminAuditLogs()]);
        setStats(statsData);
        setAuditLogs(logsData.logs.slice(0, 5)); // Just recent ones for overview
      } else if (activeTab === 'users') {
        const usersData = await getAdminUsers();
        setUsers(usersData.users);
      } else if (activeTab === 'repos') {
        const reposData = await getAdminRepos();
        setRepos(reposData.repos);
      } else if (activeTab === 'rules') {
        const rulesData = await getAdminRules();
        setRules(rulesData.rules);
      } else if (activeTab === 'audit') {
        const logsData = await getAdminAuditLogs();
        setAuditLogs(logsData.logs);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle temporary success messages
  const showSuccess = (msg) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 5000);
  };

  const handleError = (err) => {
    setError(err.response?.data?.detail || err.message || 'An error occurred');
    setTimeout(() => setError(''), 5000);
  };

  // Actions
  const handleDeleteUser = async () => {
    const { userId } = confirmModal.data;
    try {
      await adminDeleteUser(userId);
      showSuccess('User deleted successfully. All orphaned projects were removed.');
      fetchData();
    } catch (err) {
      handleError(err);
    }
  };

  const handleDeleteRepo = async () => {
    const { projectId } = confirmModal.data;
    try {
      await adminDeleteRepo(projectId);
      showSuccess('Repository and all analyses deleted successfully.');
      fetchData();
    } catch (err) {
      handleError(err);
    }
  };

  const handleDeleteAllRepos = async () => {
    try {
      await adminDeleteAllRepos();
      showSuccess('All repositories have been wiped from the system.');
      fetchData();
    } catch (err) {
      handleError(err);
    }
  };

  const handleDeleteRule = async () => {
    const { ruleId } = confirmModal.data;
    try {
      await adminDeleteRule(ruleId);
      showSuccess('Rule permanently deleted.');
      fetchData();
    } catch (err) {
      handleError(err);
    }
  };

  const handleToggleRule = async (ruleId) => {
    try {
        await adminToggleRule(ruleId);
        fetchData();
    } catch(err) {
        handleError(err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImportLoading(true);
    try {
        let res;
        if (file.name.endsWith('.json')) {
            const text = await file.text();
            let jsonRules;
            try {
                jsonRules = JSON.parse(text);
                if (!Array.isArray(jsonRules)) throw new Error("JSON must be an array of rules");
            } catch(e) {
                throw new Error("Invalid JSON file: " + e.message);
            }
            res = await adminBulkImportRulesJson(jsonRules);
        } else if (file.name.endsWith('.csv')) {
            res = await adminBulkImportRulesCsv(file);
        } else {
            throw new Error("Unsupported file type. Use .json or .csv");
        }
        
        showSuccess(`Import complete: ${res.created} created, ${res.skipped} skipped, ${res.errors_count} errors.`);
        fetchData();
    } catch(err) {
        handleError(err);
    } finally {
        setImportLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Rendering Helpers
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
  };

  const tabs = [
    { id: 'overview', icon: Activity, label: 'Overview' },
    { id: 'users', icon: UsersIcon, label: 'Users' },
    { id: 'repos', icon: HardDrive, label: 'Repositories' },
    { id: 'rules', icon: FileJson, label: 'Rules' },
    { id: 'audit', icon: Terminal, label: 'Audit Log' },
  ];

  return (
    <div className="adm-container">
      {/* ─── Header ─────────────────────────── */}
      <div className="adm-header">
        <div className="adm-header-left">
          <motion.div className="adm-header-icon"
            initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}>
            <ShieldAlert size={22} />
          </motion.div>
          <div>
            <motion.h1 className="adm-title"
              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1, duration: 0.4 }}>
              System Administration
            </motion.h1>
            <motion.p className="adm-subtitle"
              initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15, duration: 0.4 }}>
              Manage users, repositories, rules & system storage
            </motion.p>
          </div>
        </div>
        <motion.button className="adm-refresh-btn" onClick={fetchData} title="Refresh Data"
          initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
          whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}>
          <RefreshCw size={15} className={loading ? 'spin' : ''} />
          <span>Refresh</span>
        </motion.button>
      </div>

      {/* ─── Notices ────────────────────────── */}
      <AnimatePresence>
        {(error || success) && (
          <motion.div 
            className={`adm-notice ${error ? 'adm-notice-error' : 'adm-notice-success'}`}
            initial={{ opacity: 0, y: -8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -8, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="adm-notice-icon">
              {error ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
            </div>
            <span>{error || success}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── Tabs ───────────────────────────── */}
      <div className="adm-tabs">
        <div className="adm-tabs-inner">
          {tabs.map((tab, i) => (
            <motion.button 
              key={tab.id}
              className={`adm-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i, duration: 0.3 }}
              whileTap={{ scale: 0.97 }}
            >
              <tab.icon size={15} />
              <span>{tab.label}</span>
              {activeTab === tab.id && (
                <motion.div className="adm-tab-indicator" layoutId="activeTab"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }} />
              )}
            </motion.button>
          ))}
        </div>
      </div>

      {/* ─── Content Area ───────────────────── */}
      <div className="adm-content">
        {loading && !stats && !users.length && !repos.length && !rules.length && !auditLogs.length ? (
          <div className="adm-loading">
            <div className="adm-loading-spinner">
              <RefreshCw size={24} className="spin" />
            </div>
            <p>Loading {activeTab} data...</p>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {/* ═══ OVERVIEW TAB ═══ */}
            {activeTab === 'overview' && stats && (
              <motion.div key="overview"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}
                className="adm-overview">
                
                <div className="adm-stats-grid">
                  {[
                    { icon: UsersIcon, value: stats.total_users, label: 'Total Users', gradient: 'linear-gradient(135deg, #6366f1, #818cf8)', glow: 'rgba(99, 102, 241, 0.15)' },
                    { icon: HardDrive, value: stats.total_projects, label: 'Repositories', gradient: 'linear-gradient(135deg, #10b981, #34d399)', glow: 'rgba(16, 185, 129, 0.15)' },
                    { icon: Database, value: formatBytes(stats.total_storage_bytes), label: 'Storage Used', gradient: 'linear-gradient(135deg, #f97316, #fb923c)', glow: 'rgba(249, 115, 22, 0.15)' },
                    { icon: FileJson, value: stats.total_analyses, label: 'Total Analyses', gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)', glow: 'rgba(6, 182, 212, 0.15)' },
                  ].map((card, i) => (
                    <motion.div className="adm-stat-card" key={card.label}
                      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.08 * i, duration: 0.4 }}
                      style={{ '--card-glow': card.glow }}>
                      <div className="adm-stat-card-icon" style={{ background: card.gradient }}>
                        <card.icon size={20} />
                      </div>
                      <div className="adm-stat-card-body">
                        <span className="adm-stat-card-value">{card.value}</span>
                        <span className="adm-stat-card-label">{card.label}</span>
                      </div>
                    </motion.div>
                  ))}
                </div>

                <div className="adm-section">
                  <div className="adm-section-header">
                    <h3 className="adm-section-title">
                      <TrendingUp size={16} /> Recent Activity
                    </h3>
                    <button className="adm-section-link" onClick={() => setActiveTab('audit')}>
                      View all <ChevronRight size={14} />
                    </button>
                  </div>
                  {auditLogs.length > 0 ? (
                    <div className="adm-table-wrap">
                      <table className="adm-table">
                        <thead>
                          <tr>
                            <th>Time</th>
                            <th>Admin</th>
                            <th>Action</th>
                            <th>Target</th>
                          </tr>
                        </thead>
                        <tbody>
                          {auditLogs.map((log) => (
                            <tr key={log.id}>
                              <td className="adm-cell-time">{formatDate(log.created_at)}</td>
                              <td><span className="adm-badge adm-badge-purple">{log.admin_username}</span></td>
                              <td><span className="adm-badge adm-badge-slate">{log.action}</span></td>
                              <td><span className="adm-cell-mono">{log.target_type}: {log.target_id || 'all'}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="adm-empty-text">No recent activity.</p>}
                </div>
              </motion.div>
            )}

            {/* ═══ USERS TAB ═══ */}
            {activeTab === 'users' && (
              <motion.div key="users"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}
                className="adm-users">
                <div className="adm-section-header" style={{ marginBottom: 16 }}>
                  <h3 className="adm-section-title">
                    <UsersIcon size={16} /> {users.length} Registered User{users.length !== 1 ? 's' : ''}
                  </h3>
                </div>
                <div className="adm-table-wrap">
                  <table className="adm-table">
                    <thead>
                      <tr>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Joined</th>
                        <th>Repos</th>
                        <th>Storage</th>
                        <th style={{ width: 100 }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => (
                        <tr key={u.id} className={u.is_admin ? 'adm-row-admin' : ''}>
                          <td>
                            <div className="adm-user-cell">
                              <div className="adm-user-avatar">{u.username.charAt(0).toUpperCase()}</div>
                              <div>
                                <span className="adm-user-name">{u.username}</span>
                                {u.is_admin && <span className="adm-badge adm-badge-purple" style={{ marginLeft: 8, fontSize: '0.65rem' }}>ADMIN</span>}
                              </div>
                            </div>
                          </td>
                          <td className="adm-cell-secondary">{u.email}</td>
                          <td className="adm-cell-secondary">{new Date(u.created_at).toLocaleDateString()}</td>
                          <td><span className="adm-cell-metric">{u.repo_count}</span></td>
                          <td><span className="adm-cell-metric">{formatBytes(u.storage_bytes)}</span></td>
                          <td>
                            <button 
                              className="adm-btn-danger-sm"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteUser', userId: u.id, username: u.username }
                              })}
                              disabled={u.is_admin || u.id === user?.id}
                              title={u.is_admin ? "Cannot delete admins" : "Delete User"}
                            >
                              <Trash2 size={13} /> Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* ═══ REPOSITORIES TAB ═══ */}
            {activeTab === 'repos' && (
              <motion.div key="repos"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}
                className="adm-repos">
                <div className="adm-section-header" style={{ marginBottom: 16 }}>
                  <h3 className="adm-section-title">
                    <HardDrive size={16} /> {repos.length} Repositor{repos.length !== 1 ? 'ies' : 'y'}
                  </h3>
                  <button 
                    className="adm-btn-nuke"
                    onClick={() => setConfirmModal({
                      isOpen: true,
                      data: { type: 'deleteAllRepos' }
                    })}
                  >
                    <AlertTriangle size={14} /> Wipe All
                  </button>
                </div>
                
                <div className="adm-table-wrap">
                  <table className="adm-table">
                    <thead>
                      <tr>
                        <th>Repository</th>
                        <th>Collaborators</th>
                        <th>Analyses</th>
                        <th>Issues</th>
                        <th>Storage</th>
                        <th style={{ width: 80 }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {repos.map(r => (
                        <tr key={r.id}>
                          <td>
                            <div className="adm-repo-cell">
                              <span className="adm-repo-name">{r.repo_name}</span>
                              <span className="adm-repo-url">{r.repo_url}</span>
                            </div>
                          </td>
                          <td>
                            <div className="adm-collab-chips">
                              {r.users.map(u => (
                                <span key={u.id} className="adm-badge adm-badge-slate">{u.username} <span className="adm-badge-role">({u.role})</span></span>
                              ))}
                            </div>
                          </td>
                          <td><span className="adm-cell-metric">{r.analysis_count}</span></td>
                          <td>
                            {r.total_issues > 0 ? (
                              <span className="adm-badge adm-badge-orange">{r.total_issues}</span>
                            ) : <span className="adm-cell-secondary">—</span>}
                          </td>
                          <td><span className="adm-cell-metric">{formatBytes(r.storage_bytes)}</span></td>
                          <td>
                            <button 
                              className="adm-btn-danger-sm"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteRepo', projectId: r.id, repoName: r.repo_name }
                              })}
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* ═══ RULES TAB ═══ */}
            {activeTab === 'rules' && (
              <motion.div key="rules"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}
                className="adm-rules">
                <div className="adm-section-header" style={{ marginBottom: 16 }}>
                  <h3 className="adm-section-title">
                    <FileJson size={16} /> {rules.length} Analysis Rule{rules.length !== 1 ? 's' : ''}
                  </h3>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input 
                      type="file" 
                      ref={fileInputRef} 
                      style={{ display: 'none'}} 
                      accept=".json,.csv"
                      onChange={handleFileUpload}
                    />
                    <button 
                      className="adm-btn-import"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={importLoading}
                    >
                      {importLoading ? <RefreshCw size={14} className="spin" /> : <Upload size={14} />}
                      <span>Import Rules</span>
                    </button>
                  </div>
                </div>

                <div className="adm-table-wrap">
                  <table className="adm-table adm-table-compact">
                    <thead>
                      <tr>
                        <th style={{ width: 90 }}>Status</th>
                        <th>Rule ID / Name</th>
                        <th>Language / Family</th>
                        <th>Severity</th>
                        <th style={{ width: 60 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map(r => (
                        <tr key={r.id} className={!r.is_active ? 'adm-row-inactive' : ''}>
                          <td>
                            <button 
                              onClick={() => handleToggleRule(r.rule_id)}
                              className={`adm-toggle ${r.is_active ? 'adm-toggle-active' : 'adm-toggle-inactive'}`}
                            >   
                              <span className="adm-toggle-dot" />
                              {r.is_active ? 'Active' : 'Off'}
                            </button>
                          </td>
                          <td>
                            <div className="adm-rule-cell">
                              <code className="adm-rule-id">{r.rule_id}</code>
                              <span className="adm-rule-name">{r.name}</span>
                            </div>
                          </td>
                          <td>
                            <div className="adm-rule-meta">
                              <span className="adm-rule-lang">{r.language} <span style={{ opacity: 0.4 }}>•</span> {r.defect_family.replace('_', ' ')}</span>
                              <code className="adm-rule-pattern">{r.pattern}</code>
                            </div>
                          </td>
                          <td><span className={`badge badge-${r.severity}`}>{r.severity}</span></td>
                          <td>
                            <button 
                              className="adm-btn-danger-icon"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteRule', ruleId: r.rule_id }
                              })}
                              title="Delete rule"
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* ═══ AUDIT LOG TAB ═══ */}
            {activeTab === 'audit' && (
              <motion.div key="audit"
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -12 }} transition={{ duration: 0.3 }}
                className="adm-audit">
                <div className="adm-section-header" style={{ marginBottom: 16 }}>
                  <h3 className="adm-section-title">
                    <Terminal size={16} /> {auditLogs.length} Log Entr{auditLogs.length !== 1 ? 'ies' : 'y'}
                  </h3>
                </div>
                <div className="adm-table-wrap">
                  <table className="adm-table adm-table-compact">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Admin</th>
                        <th>Action</th>
                        <th>Target</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLogs.map((log) => (
                        <tr key={log.id}>
                          <td className="adm-cell-time">{formatDate(log.created_at)}</td>
                          <td><span className="adm-badge adm-badge-purple">{log.admin_username}</span></td>
                          <td><span className="adm-badge adm-badge-slate">{log.action}</span></td>
                          <td><span className="adm-cell-mono">{log.target_type}: {log.target_id || 'all'}</span></td>
                          <td>
                            <div className="adm-cell-json">
                              {log.details ? JSON.stringify(log.details) : '{}'}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>

      {/* ─── Confirmation Modals ──────────── */}
      <ConfirmModal 
        isOpen={confirmModal.isOpen && confirmModal.data?.type === 'deleteUser'}
        title="Delete User"
        message={`Are you sure you want to permanently delete user "${confirmModal.data?.username}"? This will delete all their unshared projects from physical storage. This action is irreversible.`}
        confirmText="Delete User"
        isDestructive={true}
        onClose={() => setConfirmModal({ isOpen: false, data: null })}
        onConfirm={handleDeleteUser}
      />

      <ConfirmModal 
        isOpen={confirmModal.isOpen && confirmModal.data?.type === 'deleteRepo'}
        title="Delete Repository"
        message={`Are you sure you want to permanently delete the repository "${confirmModal.data?.repoName}"? This will remove all associated analyses and cloned files from physical storage. This action is irreversible.`}
        confirmText="Delete Repository"
        isDestructive={true}
        onClose={() => setConfirmModal({ isOpen: false, data: null })}
        onConfirm={handleDeleteRepo}
      />

      <ConfirmModal 
        isOpen={confirmModal.isOpen && confirmModal.data?.type === 'deleteAllRepos'}
        title="NUCLEAR OPTION: Delete All Repositories"
        message="WARNING: This will permanently delete ALL repositories, ALL analyses, and WIPE the physical repository storage folder. This action cannot be undone."
        confirmText="WIPE ALL DATA"
        isDestructive={true}
        requireTypeToConfirm="DELETE_ALL"
        onClose={() => setConfirmModal({ isOpen: false, data: null })}
        onConfirm={handleDeleteAllRepos}
      />

      <ConfirmModal 
        isOpen={confirmModal.isOpen && confirmModal.data?.type === 'deleteRule'}
        title="Delete Analysis Rule"
        message={`Are you sure you want to permanently delete rule "${confirmModal.data?.ruleId}"? Note: you can simply toggle it inactive instead.`}
        confirmText="Delete Rule"
        isDestructive={true}
        onClose={() => setConfirmModal({ isOpen: false, data: null })}
        onConfirm={handleDeleteRule}
      />

      <style>{adminStyles}</style>
    </div>
  );
}

const adminStyles = `
  /* ═══════════════════════════════════════════
     Admin Page — Premium Design System
     ═══════════════════════════════════════════ */

  .adm-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 40px 28px 60px;
    min-height: calc(100vh - 64px);
  }

  /* ─── Header ─────────────────────────────── */
  .adm-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 32px;
    gap: 16px;
  }
  .adm-header-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .adm-header-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    background: var(--ca-gradient-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.25);
  }
  .adm-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--ca-text);
    margin: 0;
    letter-spacing: -0.5px;
    line-height: 1.2;
  }
  .adm-subtitle {
    color: var(--ca-text-muted);
    font-size: 0.88rem;
    margin-top: 2px;
  }
  .adm-refresh-btn {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 9px 18px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    color: var(--ca-text-secondary);
    font-weight: 500;
    font-size: 0.85rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .adm-refresh-btn:hover {
    border-color: var(--ca-primary);
    color: var(--ca-primary);
    background: rgba(99, 102, 241, 0.06);
  }

  /* ─── Notices ────────────────────────────── */
  .adm-notice {
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 500;
    font-size: 0.88rem;
    overflow: hidden;
  }
  .adm-notice-icon {
    flex-shrink: 0;
    display: flex;
  }
  .adm-notice-error {
    background: rgba(239, 68, 68, 0.08);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.15);
  }
  .adm-notice-success {
    background: rgba(16, 185, 129, 0.08);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.15);
  }

  /* ─── Tabs ───────────────────────────────── */
  .adm-tabs {
    margin-bottom: 24px;
    overflow-x: auto;
  }
  .adm-tabs-inner {
    display: flex;
    gap: 4px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 14px;
    padding: 4px;
    width: fit-content;
    min-width: 100%;
  }
  .adm-tab {
    position: relative;
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 10px 18px;
    background: transparent;
    border: none;
    border-radius: 10px;
    color: var(--ca-text-muted);
    font-weight: 500;
    font-size: 0.85rem;
    cursor: pointer;
    font-family: inherit;
    transition: color 0.2s;
    white-space: nowrap;
    flex: 1;
    justify-content: center;
    z-index: 1;
  }
  .adm-tab:hover:not(.active) {
    color: var(--ca-text);
  }
  .adm-tab.active {
    color: white;
  }
  .adm-tab-indicator {
    position: absolute;
    inset: 0;
    background: var(--ca-gradient-primary);
    border-radius: 10px;
    z-index: -1;
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.25);
  }

  /* ─── Content ────────────────────────────── */
  .adm-content {
    min-height: 400px;
  }
  .adm-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 340px;
    color: var(--ca-text-muted);
    gap: 16px;
    font-size: 0.9rem;
  }
  .adm-loading-spinner {
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

  /* ─── Stats Grid (Overview) ──────────────── */
  .adm-stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 32px;
  }
  .adm-stat-card {
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 16px;
    padding: 22px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: all 0.25s ease;
  }
  .adm-stat-card:hover {
    border-color: var(--ca-glass-border);
    box-shadow: 0 8px 32px var(--card-glow, rgba(0,0,0,0.1)), var(--ca-shadow-sm);
    transform: translateY(-2px);
  }
  .adm-stat-card-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    flex-shrink: 0;
  }
  .adm-stat-card-body {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .adm-stat-card-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: var(--ca-text);
    line-height: 1.15;
    letter-spacing: -0.3px;
  }
  .adm-stat-card-label {
    font-size: 0.82rem;
    color: var(--ca-text-muted);
    margin-top: 2px;
  }

  /* ─── Sections ───────────────────────────── */
  .adm-section {
    margin-top: 8px;
  }
  .adm-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .adm-section-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--ca-text);
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
    letter-spacing: -0.2px;
  }
  .adm-section-title svg {
    color: var(--ca-primary-light);
  }
  .adm-section-link {
    display: flex;
    align-items: center;
    gap: 4px;
    background: none;
    border: none;
    color: var(--ca-primary-light);
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: opacity 0.15s;
    padding: 4px 0;
  }
  .adm-section-link:hover {
    opacity: 0.8;
  }
  .adm-empty-text {
    color: var(--ca-text-muted);
    font-size: 0.9rem;
    padding: 24px 0;
  }

  /* ─── Tables ─────────────────────────────── */
  .adm-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--ca-border);
    border-radius: 14px;
    background: var(--ca-bg-card);
    margin-top: 12px;
  }
  .adm-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  .adm-table th,
  .adm-table td {
    padding: 14px 18px;
    border-bottom: 1px solid var(--ca-border);
  }
  .adm-table-compact th,
  .adm-table-compact td {
    padding: 12px 16px;
  }
  .adm-table th {
    background: var(--ca-bg-secondary);
    color: var(--ca-text-muted);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .adm-table th:first-child {
    border-radius: 14px 0 0 0;
  }
  .adm-table th:last-child {
    border-radius: 0 14px 0 0;
  }
  .adm-table tr:last-child td {
    border-bottom: none;
  }
  .adm-table tbody tr {
    transition: background 0.15s;
  }
  .adm-table tbody tr:hover {
    background: rgba(99, 102, 241, 0.02);
  }

  /* Row variants */
  .adm-row-admin td {
    background: rgba(99, 102, 241, 0.03);
  }
  .adm-row-inactive {
    opacity: 0.5;
  }
  .adm-row-inactive:hover {
    opacity: 0.7;
  }

  /* ─── Table Cells ────────────────────────── */
  .adm-cell-time {
    white-space: nowrap;
    font-size: 0.82rem;
    color: var(--ca-text-secondary);
  }
  .adm-cell-mono {
    font-family: var(--ca-font-mono);
    font-size: 0.78rem;
    color: var(--ca-text-muted);
  }
  .adm-cell-secondary {
    color: var(--ca-text-muted);
    font-size: 0.88rem;
  }
  .adm-cell-metric {
    font-weight: 600;
    font-size: 0.88rem;
    color: var(--ca-text);
  }
  .adm-cell-json {
    font-family: var(--ca-font-mono);
    font-size: 0.72rem;
    background: var(--ca-bg-secondary);
    padding: 8px 10px;
    border-radius: 8px;
    max-height: 64px;
    overflow-y: auto;
    color: var(--ca-text-muted);
    line-height: 1.5;
    word-break: break-all;
  }

  /* ─── User Cell ──────────────────────────── */
  .adm-user-cell {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .adm-user-avatar {
    width: 32px;
    height: 32px;
    border-radius: 9px;
    background: var(--ca-gradient-primary);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 600;
    flex-shrink: 0;
  }
  .adm-user-name {
    font-weight: 600;
    color: var(--ca-text);
    font-size: 0.9rem;
  }

  /* ─── Repo Cell ──────────────────────────── */
  .adm-repo-cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .adm-repo-name {
    font-weight: 600;
    color: var(--ca-text);
    font-size: 0.9rem;
  }
  .adm-repo-url {
    font-size: 0.75rem;
    color: var(--ca-text-muted);
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .adm-collab-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  /* ─── Rule Cell ──────────────────────────── */
  .adm-rule-cell {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .adm-rule-id {
    font-family: var(--ca-font-mono);
    font-size: 0.72rem;
    color: var(--ca-primary-light);
    background: rgba(99, 102, 241, 0.08);
    padding: 1px 6px;
    border-radius: 4px;
    width: fit-content;
  }
  .adm-rule-name {
    font-weight: 500;
    color: var(--ca-text);
    font-size: 0.88rem;
  }
  .adm-rule-meta {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .adm-rule-lang {
    font-size: 0.82rem;
    color: var(--ca-text-secondary);
    text-transform: capitalize;
  }
  .adm-rule-pattern {
    font-family: var(--ca-font-mono);
    font-size: 0.7rem;
    color: var(--ca-text-muted);
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    display: block;
  }

  /* ─── Toggle Button ──────────────────────── */
  .adm-toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    border: 1px solid;
    transition: all 0.2s;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .adm-toggle-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .adm-toggle-active {
    background: rgba(16, 185, 129, 0.1);
    color: #34d399;
    border-color: rgba(16, 185, 129, 0.25);
  }
  .adm-toggle-active .adm-toggle-dot {
    background: #34d399;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
  }
  .adm-toggle-active:hover {
    background: rgba(16, 185, 129, 0.15);
  }
  .adm-toggle-inactive {
    background: var(--ca-bg-secondary);
    color: var(--ca-text-muted);
    border-color: var(--ca-border);
  }
  .adm-toggle-inactive .adm-toggle-dot {
    background: var(--ca-text-muted);
  }
  .adm-toggle-inactive:hover {
    border-color: var(--ca-text-muted);
  }

  /* ─── Badges ─────────────────────────────── */
  .adm-badge {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
  }
  .adm-badge-purple {
    background: rgba(139, 92, 246, 0.1);
    color: #a78bfa;
    border: 1px solid rgba(139, 92, 246, 0.2);
  }
  .adm-badge-slate {
    background: rgba(100, 116, 139, 0.1);
    color: var(--ca-text-secondary);
    border: 1px solid rgba(100, 116, 139, 0.2);
  }
  .adm-badge-orange {
    background: rgba(249, 115, 22, 0.12);
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.25);
  }
  .adm-badge-role {
    opacity: 0.6;
    font-weight: 400;
  }

  /* ─── Action Buttons ─────────────────────── */
  .adm-btn-danger-sm {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    background: rgba(239, 68, 68, 0.08);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.12);
    border-radius: 8px;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
  }
  .adm-btn-danger-sm:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.3);
    color: #ef4444;
  }
  .adm-btn-danger-sm:disabled {
    opacity: 0.25;
    cursor: not-allowed;
  }

  .adm-btn-danger-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    background: transparent;
    color: var(--ca-text-muted);
    border: 1px solid transparent;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .adm-btn-danger-icon:hover {
    background: rgba(239, 68, 68, 0.1);
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.2);
  }

  .adm-btn-nuke {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: rgba(239, 68, 68, 0.08);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.15);
    border-radius: 10px;
    font-weight: 600;
    font-size: 0.8rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
  }
  .adm-btn-nuke:hover {
    background: #ef4444;
    color: white;
    border-color: #ef4444;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.3);
  }

  .adm-btn-import {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 16px;
    background: var(--ca-bg-elevated);
    color: var(--ca-text-secondary);
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    font-weight: 500;
    font-size: 0.82rem;
    cursor: pointer;
    font-family: inherit;
    transition: all 0.2s;
  }
  .adm-btn-import:hover:not(:disabled) {
    border-color: var(--ca-primary);
    color: var(--ca-primary);
    background: rgba(99, 102, 241, 0.06);
  }
  .adm-btn-import:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* ─── Modal Styles (kept for ConfirmModal) ────── */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
    z-index: 100;
  }
  .modal-wrapper {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 101;
    padding: 20px;
  }
  .modal-content {
    background: var(--ca-bg-elevated);
    max-width: 480px;
    width: 100%;
    padding: 28px;
    border-radius: 18px;
    border: 1px solid var(--ca-border);
    box-shadow: var(--ca-shadow-lg);
  }
  .modal-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 16px;
  }
  .modal-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .modal-icon.destructive {
    background: rgba(239, 68, 68, 0.12);
    color: #ef4444;
  }
  .modal-title {
    font-size: 1.15rem;
    margin: 0;
    font-weight: 600;
    letter-spacing: -0.2px;
  }
  .modal-body {
    color: var(--ca-text-secondary);
    margin-bottom: 24px;
    line-height: 1.6;
    font-size: 0.92rem;
  }
  .modal-type-confirm {
    margin-top: 16px;
    padding: 16px;
    background: var(--ca-bg-secondary);
    border-radius: 12px;
    border: 1px dashed var(--ca-border);
  }
  .modal-type-confirm label {
    display: block;
    margin-bottom: 8px;
    font-size: 0.88rem;
    color: var(--ca-text);
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }
  .btn-destructive {
    background: #ef4444;
    color: white;
  }
  .btn-destructive:hover:not(:disabled) {
    background: #dc2626;
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.3);
  }

  /* ─── Animations ─────────────────────────── */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.8s linear infinite; }

  /* ─── Responsive ─────────────────────────── */
  @media (max-width: 768px) {
    .adm-container { padding: 24px 16px 60px; }
    .adm-header { flex-direction: column; align-items: flex-start; }
    .adm-stats-grid { grid-template-columns: repeat(2, 1fr); }
    .adm-tabs-inner { min-width: fit-content; }
    .adm-tab { padding: 8px 14px; font-size: 0.8rem; }
  }
  @media (max-width: 480px) {
    .adm-stats-grid { grid-template-columns: 1fr; }
    .adm-header-icon { width: 40px; height: 40px; border-radius: 12px; }
    .adm-title { font-size: 1.3rem; }
  }
`;
