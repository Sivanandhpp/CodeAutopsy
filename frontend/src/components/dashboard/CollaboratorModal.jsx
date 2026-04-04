/**
 * CollaboratorModal — Manage Project Team Members
 * ==================================================
 * Search users by username, add/remove collaborators with roles.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Search, UserPlus, Trash2, Loader2, Users } from 'lucide-react';
import { searchUsers, addCollaborator, removeCollaborator } from '../../lib/api';
import useAuthStore from '../../lib/authStore';

export default function CollaboratorModal({ project, onClose, onUpdate }) {
  const { user } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedRole, setSelectedRole] = useState('viewer');
  const [adding, setAdding] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [error, setError] = useState('');
  const debounceRef = useRef(null);

  // Debounced search
  useEffect(() => {
    if (searchQuery.length < 2) {
      setSearchResults([]);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await searchUsers(searchQuery);
        // Filter out existing collaborators
        const existingIds = new Set((project.collaborators || []).map(c => c.user_id));
        setSearchResults((data.users || []).filter(u => !existingIds.has(u.id)));
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchQuery, project.collaborators]);

  const handleAdd = async (targetUser) => {
    setAdding(targetUser.id);
    setError('');
    try {
      await addCollaborator(project.id, targetUser.username, selectedRole);
      setSearchQuery('');
      setSearchResults([]);
      onUpdate();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add collaborator');
    } finally {
      setAdding(null);
    }
  };

  const handleRemove = async (userId) => {
    setRemoving(userId);
    setError('');
    try {
      await removeCollaborator(project.id, userId);
      onUpdate();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove collaborator');
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div className="cm-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <motion.div className="cm-modal"
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}>

        {/* Header */}
        <div className="cm-header">
          <div>
            <h3 className="cm-title"><Users size={18} /> Manage Team</h3>
            <p className="cm-project-name">{project.repo_name}</p>
          </div>
          <button className="cm-close" onClick={onClose}><X size={18} /></button>
        </div>

        {/* Search */}
        <div className="cm-search-section">
          <div className="cm-search-bar">
            <Search size={16} />
            <input type="text" placeholder="Search users by username..."
              value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} autoFocus />
          </div>

          <div className="cm-role-select">
            {['viewer', 'editor'].map(role => (
              <button key={role}
                className={`cm-role-btn ${selectedRole === role ? 'active' : ''}`}
                onClick={() => setSelectedRole(role)}>
                {role.charAt(0).toUpperCase() + role.slice(1)}
              </button>
            ))}
          </div>

          {/* Search Results */}
          {searchResults.length > 0 && (
            <div className="cm-results">
              {searchResults.map(u => (
                <div key={u.id} className="cm-result-item">
                  <div className="cm-result-avatar">{u.username.charAt(0).toUpperCase()}</div>
                  <div className="cm-result-info">
                    <span className="cm-result-name">{u.username}</span>
                    <span className="cm-result-email">{u.email}</span>
                  </div>
                  <button className="cm-add-btn" onClick={() => handleAdd(u)}
                    disabled={adding === u.id}>
                    {adding === u.id ? <Loader2 size={14} className="spin" /> : <UserPlus size={14} />}
                  </button>
                </div>
              ))}
            </div>
          )}
          {searching && <p className="cm-hint"><Loader2 size={14} className="spin" /> Searching...</p>}
        </div>

        {error && <p className="cm-error">{error}</p>}

        {/* Current Team */}
        <div className="cm-team">
          <h4 className="cm-team-title">Current Team ({project.collaborators?.length || 0})</h4>
          {(project.collaborators || []).map(c => (
            <div key={c.user_id} className="cm-member">
              <div className="cm-member-avatar">{c.username.charAt(0).toUpperCase()}</div>
              <div className="cm-member-info">
                <span className="cm-member-name">
                  {c.username} {c.user_id === user?.id && <span className="cm-you">(you)</span>}
                </span>
                <span className="cm-member-role" data-role={c.role}>{c.role}</span>
              </div>
              {c.role !== 'owner' && c.user_id !== user?.id && (
                <button className="cm-remove-btn" onClick={() => handleRemove(c.user_id)}
                  disabled={removing === c.user_id}>
                  {removing === c.user_id ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
                </button>
              )}
            </div>
          ))}
        </div>
      </motion.div>

      <style>{modalStyles}</style>
    </div>
  );
}

const modalStyles = `
  .cm-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 24px;
  }

  .cm-modal {
    background: var(--ca-bg-card);
    border: 1px solid var(--ca-border);
    border-radius: 20px;
    width: 100%;
    max-width: 480px;
    max-height: 80vh;
    overflow-y: auto;
    padding: 24px;
  }

  .cm-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }
  .cm-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.15rem;
    color: var(--ca-text);
    margin: 0;
  }
  .cm-project-name {
    font-size: 0.85rem;
    color: var(--ca-text-muted);
    margin-top: 4px;
  }
  .cm-close {
    background: transparent;
    border: none;
    color: var(--ca-text-muted);
    cursor: pointer;
    padding: 4px;
    border-radius: 8px;
    display: flex;
  }
  .cm-close:hover { color: var(--ca-text); }

  .cm-search-section { margin-bottom: 16px; }
  .cm-search-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: var(--ca-bg-secondary);
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    color: var(--ca-text-muted);
    margin-bottom: 8px;
  }
  .cm-search-bar input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--ca-text);
    font-size: 0.9rem;
    font-family: inherit;
    width: 100%;
  }
  .cm-role-select { display: flex; gap: 4px; margin-bottom: 8px; }
  .cm-role-btn {
    padding: 4px 12px;
    border: 1px solid var(--ca-border);
    border-radius: 6px;
    background: transparent;
    color: var(--ca-text-muted);
    font-size: 0.78rem;
    cursor: pointer;
    font-family: inherit;
  }
  .cm-role-btn.active { background: var(--ca-primary); border-color: var(--ca-primary); color: white; }

  .cm-results {
    border: 1px solid var(--ca-border);
    border-radius: 10px;
    overflow: hidden;
  }
  .cm-result-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-bottom: 1px solid var(--ca-border);
  }
  .cm-result-item:last-child { border-bottom: none; }
  .cm-result-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 600;
    flex-shrink: 0;
  }
  .cm-result-info { flex: 1; display: flex; flex-direction: column; }
  .cm-result-name { font-size: 0.9rem; color: var(--ca-text); font-weight: 500; }
  .cm-result-email { font-size: 0.78rem; color: var(--ca-text-muted); }
  .cm-add-btn {
    padding: 6px;
    background: transparent;
    border: 1px solid var(--ca-border);
    border-radius: 6px;
    cursor: pointer;
    color: var(--ca-primary);
    display: flex;
  }
  .cm-add-btn:hover { background: rgba(99, 102, 241, 0.1); }
  .cm-hint { font-size: 0.82rem; color: var(--ca-text-muted); display: flex; align-items: center; gap: 6px; }
  .cm-error { color: #f87171; font-size: 0.85rem; margin: 8px 0; }

  .cm-team { margin-top: 8px; }
  .cm-team-title { font-size: 0.85rem; color: var(--ca-text-muted); margin: 0 0 10px; font-weight: 500; }
  .cm-member {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid var(--ca-border);
  }
  .cm-member:last-child { border-bottom: none; }
  .cm-member-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--ca-bg-elevated);
    color: var(--ca-text-secondary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 600;
    flex-shrink: 0;
  }
  .cm-member-info { flex: 1; display: flex; align-items: center; gap: 8px; }
  .cm-member-name { font-size: 0.9rem; color: var(--ca-text); }
  .cm-you { color: var(--ca-text-muted); font-size: 0.78rem; }
  .cm-member-role {
    font-size: 0.7rem;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
  }
  .cm-member-role[data-role="owner"] { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
  .cm-member-role[data-role="editor"] { background: rgba(16, 185, 129, 0.15); color: #34d399; }
  .cm-member-role[data-role="viewer"] { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }
  .cm-remove-btn {
    padding: 5px;
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--ca-text-muted);
    display: flex;
    border-radius: 6px;
  }
  .cm-remove-btn:hover { color: #ef4444; background: rgba(239, 68, 68, 0.1); }

  @keyframes spin { to { transform: rotate(360deg); } }
  .spin { animation: spin 0.8s linear infinite; }
`;
