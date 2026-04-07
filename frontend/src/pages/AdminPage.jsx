import { useState, useEffect, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import { 
  ShieldAlert, Users as UsersIcon, Database, HardDrive, 
  Trash2, RefreshCw, AlertTriangle, AlertCircle, FileJson, 
  Upload, Terminal, CheckCircle 
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

  return (
    <div className="admin-container">
      <div className="admin-header">
        <div>
          <h1 className="admin-title"><ShieldAlert size={28} /> System Administration</h1>
          <p className="admin-subtitle">Manage users, repositories, analysis rules, and system storage</p>
        </div>
        <button className="btn-secondary" onClick={fetchData} title="Refresh Data">
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {(error || success) && (
        <motion.div 
            className={`admin-notice ${error ? 'admin-error' : 'admin-success'}`}
            initial={{ opacity: 0, y: -10 }} 
            animate={{ opacity: 1, y: 0 }}
        >
            {error ? <AlertCircle size={18} /> : <CheckCircle size={18} />}
            <span>{error || success}</span>
        </motion.div>
      )}

      {/* Tabs */}
      <div className="admin-tabs">
        {[
          { id: 'overview', icon: Database, label: 'Overview' },
          { id: 'users', icon: UsersIcon, label: 'Users' },
          { id: 'repos', icon: HardDrive, label: 'Repositories' },
          { id: 'rules', icon: FileJson, label: 'Analysis Rules' },
          { id: 'audit', icon: Terminal, label: 'Audit Log' },
        ].map(tab => (
          <button 
            key={tab.id}
            className={`admin-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon size={16} /> {tab.label}
          </button>
        ))}
      </div>

      <div className="admin-content card">
        {loading && !stats && !users.length && !repos.length && !rules.length && !auditLogs.length ? (
          <div className="admin-loading">
            <RefreshCw size={32} className="spin" />
            <p>Loading {activeTab} data...</p>
          </div>
        ) : (
          <>
            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && stats && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="admin-overview">
                <div className="admin-stats-grid">
                  <div className="admin-stat-card glow-effect">
                    <div className="stat-icon users"><UsersIcon size={24} /></div>
                    <div className="stat-info">
                      <span className="stat-value">{stats.total_users}</span>
                      <span className="stat-label">Total Users</span>
                    </div>
                  </div>
                  <div className="admin-stat-card glow-effect">
                    <div className="stat-icon repos"><HardDrive size={24} /></div>
                    <div className="stat-info">
                      <span className="stat-value">{stats.total_projects}</span>
                      <span className="stat-label">Total Repositories</span>
                    </div>
                  </div>
                  <div className="admin-stat-card glow-effect">
                    <div className="stat-icon storage"><Database size={24} /></div>
                    <div className="stat-info">
                      <span className="stat-value">{formatBytes(stats.total_storage_bytes)}</span>
                      <span className="stat-label">Storage Used</span>
                    </div>
                  </div>
                  <div className="admin-stat-card glow-effect">
                    <div className="stat-icon analyses"><FileJson size={24} /></div>
                    <div className="stat-info">
                      <span className="stat-value">{stats.total_analyses}</span>
                      <span className="stat-label">Total Analyses</span>
                    </div>
                  </div>
                </div>

                <div className="admin-section mt-8">
                  <h3 className="section-title">Recent Activity</h3>
                  {auditLogs.length > 0 ? (
                    <div className="table-container">
                      <table className="admin-table">
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
                              <td>{formatDate(log.created_at)}</td>
                              <td><span className="badge badge-info">{log.admin_username}</span></td>
                              <td><span className="badge badge-trace">{log.action}</span></td>
                              <td className="mono">{log.target_type}: {log.target_id || 'all'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : <p className="text-muted">No recent activity.</p>}
                </div>
              </motion.div>
            )}

            {/* USERS TAB */}
            {activeTab === 'users' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="admin-users">
                <div className="table-container">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Username</th>
                        <th>Email</th>
                        <th>Joined</th>
                        <th>Repos</th>
                        <th>Storage Used</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {users.map(u => (
                        <tr key={u.id} className={u.is_admin ? 'is-admin-row' : ''}>
                          <td>
                            {u.username}
                            {u.is_admin && <span className="badge badge-info ml-2">ADMIN</span>}
                          </td>
                          <td>{u.email}</td>
                          <td>{new Date(u.created_at).toLocaleDateString()}</td>
                          <td>{u.repo_count}</td>
                          <td>{formatBytes(u.storage_bytes)}</td>
                          <td>
                            <button 
                              className="btn-danger-sm"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteUser', userId: u.id, username: u.username }
                              })}
                              disabled={u.is_admin || u.id === user?.id} // Prevent deleting admins/self
                              title={u.is_admin ? "Cannot delete admins" : "Delete User"}
                            >
                              <Trash2 size={14} /> Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* REPOSITORIES TAB */}
            {activeTab === 'repos' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="admin-repos">
                <div className="admin-actions-bar">
                    <button 
                        className="btn-danger"
                        onClick={() => setConfirmModal({
                            isOpen: true,
                            data: { type: 'deleteAllRepos' }
                        })}
                    >
                        <AlertTriangle size={16} /> WIPE ALL REPOSITORIES
                    </button>
                </div>
                
                <div className="table-container mt-4">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Repository</th>
                        <th>Users</th>
                        <th>Analyses</th>
                        <th>Total Issues</th>
                        <th>Storage</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {repos.map(r => (
                        <tr key={r.id}>
                          <td>
                            <strong>{r.repo_name}</strong>
                            <div className="text-xs text-muted">{r.repo_url}</div>
                          </td>
                          <td>
                            <div className="flex flex-wrap gap-1">
                                {r.users.map(u => (
                                    <span key={u.id} className="badge badge-trace">{u.username} ({u.role})</span>
                                ))}
                            </div>
                          </td>
                          <td>{r.analysis_count}</td>
                          <td>
                            {r.total_issues > 0 ? (
                                <span className="badge badge-high">{r.total_issues}</span>
                            ) : '-'}
                          </td>
                          <td>{formatBytes(r.storage_bytes)}</td>
                          <td>
                            <button 
                              className="btn-danger-sm"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteRepo', projectId: r.id, repoName: r.repo_name }
                              })}
                            >
                              <Trash2 size={14} /> Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {/* RULES TAB */}
            {activeTab === 'rules' && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="admin-rules">
                    <div className="admin-actions-bar flex justify-between items-center">
                        <div>
                            <h3 className="section-title m-0">Static Analysis Rules ({rules.length})</h3>
                        </div>
                        <div className="flex gap-2">
                            <input 
                                type="file" 
                                ref={fileInputRef} 
                                style={{ display: 'none'}} 
                                accept=".json,.csv"
                                onChange={handleFileUpload}
                            />
                            <button 
                                className="btn-secondary"
                                onClick={() => fileInputRef.current?.click()}
                                disabled={importLoading}
                            >
                                {importLoading ? <RefreshCw size={16} className="spin" /> : <Upload size={16} />}
                                Bulk Import (JSON/CSV)
                            </button>
                        </div>
                    </div>

                    <div className="table-container mt-4">
                  <table className="admin-table text-sm">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th>Rule ID / Name</th>
                        <th>Lang/Family</th>
                        <th>Severity</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rules.map(r => (
                        <tr key={r.id} className={!r.is_active ? 'opacity-50' : ''}>
                          <td>
                            <button 
                                onClick={() => handleToggleRule(r.rule_id)}
                                className={`text-xs px-2 py-1 rounded border cursor-pointer hover:opacity-80 ${r.is_active ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30' : 'bg-slate-500/10 text-slate-400 border-slate-500/30'}`}
                            >   
                                {r.is_active ? 'ACTIVE' : 'INACTIVE'}
                            </button>
                          </td>
                          <td>
                            <div className="font-mono text-xs text-primary">{r.rule_id}</div>
                            <div className="font-semibold">{r.name}</div>
                          </td>
                          <td>
                            <div className="capitalize">{r.language} • {r.defect_family.replace('_', ' ')}</div>
                            <div className="font-mono text-xs text-muted mt-1 truncate max-w-xs">{r.pattern}</div>
                          </td>
                          <td><span className={`badge badge-${r.severity}`}>{r.severity}</span></td>
                          <td>
                            <button 
                              className="btn-danger-sm"
                              onClick={() => setConfirmModal({
                                isOpen: true,
                                data: { type: 'deleteRule', ruleId: r.rule_id }
                              })}
                            >
                              <Trash2 size={12} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                </motion.div>
            )}

            {/* AUDIT LOG TAB */}
            {activeTab === 'audit' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="admin-audit">
                 <div className="table-container">
                    <table className="admin-table text-sm">
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
                            <td className="whitespace-nowrap">{formatDate(log.created_at)}</td>
                            <td><span className="badge badge-info">{log.admin_username}</span></td>
                            <td><span className="badge badge-trace">{log.action}</span></td>
                            <td className="mono">{log.target_type}: {log.target_id || 'all'}</td>
                            <td>
                                <div className="text-xs bg-black/20 p-2 rounded max-h-24 overflow-y-auto font-mono text-slate-400">
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
          </>
        )}
      </div>

      {/* Confirmation Modals */}
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
  .admin-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    min-height: calc(100vh - 64px);
  }

  .admin-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
  }

  .admin-title {
    font-size: 1.75rem;
    font-weight: 600;
    color: var(--ca-text);
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .admin-title svg {
    color: var(--ca-primary);
  }

  .admin-subtitle {
    color: var(--ca-text-muted);
    font-size: 0.95rem;
    margin-top: 4px;
  }

  .admin-notice {
    padding: 12px 16px;
    border-radius: var(--ca-radius-sm);
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }

  .admin-error {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.2);
  }

  .admin-success {
    background: rgba(16, 185, 129, 0.1);
    color: #10b981;
    border: 1px solid rgba(16, 185, 129, 0.2);
  }

  .admin-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 24px;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .admin-tab {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: var(--ca-radius-sm);
    color: var(--ca-text-muted);
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .admin-tab:hover {
    background: var(--ca-bg-elevated);
    color: var(--ca-text);
  }

  .admin-tab.active {
    background: var(--ca-primary);
    border-color: var(--ca-primary);
    color: white;
  }

  .admin-content {
    min-height: 400px;
  }

  .admin-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 300px;
    color: var(--ca-text-muted);
    gap: 16px;
  }

  /* Stats Grid */
  .admin-stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
  }

  .admin-stat-card {
    background: var(--ca-bg-elevated);
    border: 1px solid var(--ca-glass-border);
    border-radius: var(--ca-radius);
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stat-icon.users { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
  .stat-icon.repos { background: rgba(16, 185, 129, 0.15); color: #34d399; }
  .stat-icon.storage { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
  .stat-icon.analyses { background: rgba(6, 182, 212, 0.15); color: #22d3ee; }

  .stat-info {
    display: flex;
    flex-direction: column;
  }

  .stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--ca-text);
    line-height: 1.2;
  }

  .stat-label {
    font-size: 0.85rem;
    color: var(--ca-text-muted);
  }

  /* Tables */
  .table-container {
    overflow-x: auto;
    border: 1px solid var(--ca-border);
    border-radius: var(--ca-radius-sm);
    background: var(--ca-bg-elevated);
  }

  .admin-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }

  .admin-table th, .admin-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--ca-border);
  }

  .admin-table th {
    background: var(--ca-bg-secondary);
    color: var(--ca-text-secondary);
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .admin-table tr:last-child td {
    border-bottom: none;
  }

  .admin-table tr:hover td {
    background: rgba(255, 255, 255, 0.02);
  }

  .is-admin-row td {
    background: rgba(99, 102, 241, 0.03);
  }

  /* Buttons inside Admin */
  .btn-danger {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 10px 20px;
    border-radius: var(--ca-radius-sm);
    font-weight: 600;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s;
  }

  .btn-danger:hover {
    background: #ef4444;
    color: white;
  }

  .btn-danger-sm {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border: 1px solid transparent;
    padding: 6px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: all 0.15s;
  }
  
  .btn-danger-sm:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.4);
  }
  
  .btn-danger-sm:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  /* Modals Overlay for ConfirmModal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    backdrop-filter: blur(4px);
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
    max-width: 500px;
    width: 100%;
    padding: 24px;
    border-radius: var(--ca-radius);
    border: 1px solid var(--ca-border);
  }

  .modal-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
  }

  .modal-icon {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .modal-icon.destructive {
      background: rgba(239, 68, 68, 0.15);
      color: #ef4444;
  }

  .modal-title {
    font-size: 1.25rem;
    margin: 0;
  }

  .modal-body {
    color: var(--ca-text-secondary);
    margin-bottom: 24px;
    line-height: 1.6;
  }

  .modal-type-confirm {
    margin-top: 16px;
    padding: 16px;
    background: var(--ca-bg-secondary);
    border-radius: var(--ca-radius-sm);
    border: 1px dashed var(--ca-border);
  }

  .modal-type-confirm label {
    display: block;
    margin-bottom: 8px;
    font-size: 0.9rem;
    color: var(--ca-text);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }

  .btn-destructive {
    background: #ef4444;
    color: white;
  }
  .btn-destructive:hover:not(:disabled) {
    background: #dc2626;
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
  }
`;
