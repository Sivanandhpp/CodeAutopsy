import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

export default function ConfirmModal({ 
  isOpen, 
  title, 
  message, 
  confirmText = 'Confirm', 
  cancelText = 'Cancel', 
  onConfirm, 
  onClose, 
  isDestructive = false,
  requireTypeToConfirm = null // String text the user must type to confirm
}) {
  const [typedConfirm, setTypedConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setTypedConfirm('');
      setLoading(false);
    }
  }, [isOpen]);

  const handleConfirm = async () => {
    if (requireTypeToConfirm && typedConfirm !== requireTypeToConfirm) return;
    
    setLoading(true);
    try {
      await onConfirm();
    // eslint-disable-next-line no-unused-vars
    } catch (err) {
      // Error handled by parent
    } finally {
      setLoading(false);
      onClose();
    }
  };

  const isConfirmDisabled = loading || (requireTypeToConfirm && typedConfirm !== requireTypeToConfirm);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div 
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={!loading ? onClose : undefined}
          />
          
          {/* Modal */}
          <div className="modal-wrapper">
            <motion.div 
              className="modal-content glass-card"
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
            >
              <div className="modal-header">
                <div className={`modal-icon ${isDestructive ? 'destructive' : 'warning'}`}>
                  {isDestructive ? <AlertCircle size={28} /> : <CheckCircle size={28} />}
                </div>
                <h3 className="modal-title">{title}</h3>
              </div>
              
              <div className="modal-body">
                <p>{message}</p>
                
                {requireTypeToConfirm && (
                  <div className="modal-type-confirm">
                    <label>Please type <strong>{requireTypeToConfirm}</strong> to confirm.</label>
                    <input 
                      type="text" 
                      className="input" 
                      value={typedConfirm}
                      onChange={(e) => setTypedConfirm(e.target.value)}
                      placeholder={requireTypeToConfirm}
                      disabled={loading}
                    />
                  </div>
                )}
              </div>
              
              <div className="modal-actions">
                <button 
                  className="btn-secondary" 
                  onClick={onClose}
                  disabled={loading}
                >
                  {cancelText}
                </button>
                <button 
                  className={`btn-primary ${isDestructive ? 'btn-destructive' : ''}`}
                  onClick={handleConfirm}
                  disabled={isConfirmDisabled}
                >
                  {loading ? <Loader2 size={16} className="spin" /> : confirmText}
                </button>
              </div>
            </motion.div>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}
