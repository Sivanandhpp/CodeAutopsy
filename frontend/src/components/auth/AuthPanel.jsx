/**
 * AuthPanel — Frosted-Glass Floating Authentication Panel
 * =========================================================
 * Multi-step auth flow: Email → (Login | OTP → Register)
 * Expands from login button with smooth animation.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ArrowRight, ArrowLeft, Mail, Lock, User, Eye, EyeOff, Loader2, Check } from 'lucide-react';
import useAuthStore from '../../lib/authStore';
import {
  checkEmail, sendOtp, verifyOtp, registerUser,
  loginUser, forgotPassword,
} from '../../lib/api';

const STEPS = {
  EMAIL: 'email',
  LOGIN: 'login',
  OTP: 'otp',
  REGISTER: 'register',
  FORGOT: 'forgot',
  SUCCESS: 'success',
};

export default function AuthPanel({ isOpen, onClose, anchorRef }) {
  const [step, setStep] = useState(STEPS.EMAIL);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [username, setUsername] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [tempToken, setTempToken] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const panelRef = useRef(null);
  const { setAuth } = useAuthStore();

  // Close on Escape
  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  // Close on click outside
  useEffect(() => {
    const handleClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target) &&
          anchorRef?.current && !anchorRef.current.contains(e.target)) {
        onClose();
      }
    };
    if (isOpen) {
      setTimeout(() => document.addEventListener('mousedown', handleClick), 100);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen, onClose, anchorRef]);

  // Reset state on open/close
  useEffect(() => {
    if (!isOpen) {
      setTimeout(() => {
        setStep(STEPS.EMAIL);
        setEmail('');
        setPassword('');
        setUsername('');
        setOtpCode('');
        setTempToken('');
        setError('');
        setSuccessMsg('');
        setShowPassword(false);
      }, 300);
    }
  }, [isOpen]);

  const handleError = useCallback((err) => {
    const msg = err?.response?.data?.detail || err?.message || 'Something went wrong';
    setError(msg);
    setLoading(false);
  }, []);

  // ─── Step Handlers ────────────────────────────────────────

  const handleEmailSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError('');
    setLoading(true);
    try {
      const result = await checkEmail(email);
      if (result.exists) {
        setStep(STEPS.LOGIN);
      } else {
        await sendOtp(email);
        setStep(STEPS.OTP);
      }
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await loginUser(email, password);
      setAuth(result.access_token, result.user);
      setStep(STEPS.SUCCESS);
      setSuccessMsg(`Welcome back, ${result.user.username}!`);
      setTimeout(onClose, 1200);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleOtpVerify = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await verifyOtp(email, otpCode);
      setTempToken(result.temp_token);
      setStep(STEPS.REGISTER);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const result = await registerUser(email, username, password, tempToken);
      setAuth(result.access_token, result.user);
      setStep(STEPS.SUCCESS);
      setSuccessMsg(`Welcome, ${result.user.username}! 🎉`);
      setTimeout(onClose, 1200);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async () => {
    setError('');
    setLoading(true);
    try {
      await forgotPassword(email);
      setSuccessMsg('Reset code sent to your email');
      setTimeout(() => {
        setSuccessMsg('');
        setStep(STEPS.LOGIN);
      }, 2000);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    setError('');
    setLoading(true);
    try {
      await sendOtp(email);
      setSuccessMsg('New code sent!');
      setTimeout(() => setSuccessMsg(''), 2000);
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  // ─── Render Steps ─────────────────────────────────────────

  const renderStep = () => {
    const stepVariants = {
      initial: { opacity: 0, x: 20 },
      animate: { opacity: 1, x: 0, transition: { duration: 0.2 } },
      exit: { opacity: 0, x: -20, transition: { duration: 0.15 } },
    };

    switch (step) {
      case STEPS.EMAIL:
        return (
          <motion.form key="email" {...stepVariants} onSubmit={handleEmailSubmit} className="ap-form">
            <h3 className="ap-title">Welcome</h3>
            <p className="ap-subtitle">Enter your email to continue</p>
            <div className="ap-field">
              <Mail size={16} className="ap-icon" />
              <input type="email" placeholder="you@example.com" value={email}
                onChange={(e) => setEmail(e.target.value)} autoFocus required className="ap-input" />
            </div>
            <button type="submit" className="ap-btn-primary" disabled={loading || !email.trim()}>
              {loading ? <Loader2 size={16} className="ap-spin" /> : <><span>Continue</span><ArrowRight size={16} /></>}
            </button>
          </motion.form>
        );

      case STEPS.LOGIN:
        return (
          <motion.form key="login" {...stepVariants} onSubmit={handleLogin} className="ap-form">
            <button type="button" className="ap-back" onClick={() => setStep(STEPS.EMAIL)}>
              <ArrowLeft size={14} /> Back
            </button>
            <h3 className="ap-title">Welcome back</h3>
            <p className="ap-subtitle">{email}</p>
            <div className="ap-field">
              <Lock size={16} className="ap-icon" />
              <input type={showPassword ? 'text' : 'password'} placeholder="Password" value={password}
                onChange={(e) => setPassword(e.target.value)} autoFocus required className="ap-input" />
              <button type="button" className="ap-eye" onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <button type="submit" className="ap-btn-primary" disabled={loading || !password}>
              {loading ? <Loader2 size={16} className="ap-spin" /> : 'Sign In'}
            </button>
            <button type="button" className="ap-link" onClick={handleForgotPassword}>
              Forgot password?
            </button>
          </motion.form>
        );

      case STEPS.OTP:
        return (
          <motion.form key="otp" {...stepVariants} onSubmit={handleOtpVerify} className="ap-form">
            <button type="button" className="ap-back" onClick={() => setStep(STEPS.EMAIL)}>
              <ArrowLeft size={14} /> Back
            </button>
            <h3 className="ap-title">Verify Email</h3>
            <p className="ap-subtitle">Enter the 6-digit code sent to {email}</p>
            <div className="ap-field ap-otp-field">
              <input type="text" inputMode="numeric" maxLength={6} placeholder="000000" value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                autoFocus required className="ap-input ap-otp-input" />
            </div>
            <button type="submit" className="ap-btn-primary" disabled={loading || otpCode.length !== 6}>
              {loading ? <Loader2 size={16} className="ap-spin" /> : 'Verify'}
            </button>
            <button type="button" className="ap-link" onClick={handleResendOtp}>
              Resend code
            </button>
          </motion.form>
        );

      case STEPS.REGISTER:
        return (
          <motion.form key="register" {...stepVariants} onSubmit={handleRegister} className="ap-form">
            <h3 className="ap-title">Create Account</h3>
            <p className="ap-subtitle">Choose a username and password</p>
            <div className="ap-field">
              <User size={16} className="ap-icon" />
              <input type="text" placeholder="Username" value={username} minLength={3} maxLength={50}
                onChange={(e) => setUsername(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ''))}
                autoFocus required className="ap-input" />
            </div>
            <div className="ap-field">
              <Lock size={16} className="ap-icon" />
              <input type={showPassword ? 'text' : 'password'} placeholder="Password (min 8 chars)"
                value={password} minLength={8}
                onChange={(e) => setPassword(e.target.value)} required className="ap-input" />
              <button type="button" className="ap-eye" onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            <button type="submit" className="ap-btn-primary"
              disabled={loading || !username || password.length < 8}>
              {loading ? <Loader2 size={16} className="ap-spin" /> : 'Create Account'}
            </button>
          </motion.form>
        );

      case STEPS.SUCCESS:
        return (
          <motion.div key="success" {...stepVariants} className="ap-form ap-success">
            <div className="ap-success-icon"><Check size={32} /></div>
            <h3 className="ap-title">{successMsg}</h3>
          </motion.div>
        );

      default:
        return null;
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          ref={panelRef}
          className="ap-panel"
          initial={{ opacity: 0, scale: 0.9, y: -10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -10 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Close button */}
          <button className="ap-close" onClick={onClose}>
            <X size={16} />
          </button>

          {/* Step content */}
          <AnimatePresence mode="wait">
            {renderStep()}
          </AnimatePresence>

          {/* Error message */}
          <AnimatePresence>
            {error && (
              <motion.p className="ap-error"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}>
                {error}
              </motion.p>
            )}
          </AnimatePresence>

          {/* Success toast */}
          <AnimatePresence>
            {successMsg && step !== STEPS.SUCCESS && (
              <motion.p className="ap-toast"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}>
                {successMsg}
              </motion.p>
            )}
          </AnimatePresence>

          <style>{authPanelStyles}</style>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

const authPanelStyles = `
  .ap-panel {
    position: fixed;
    top: 64px;
    right: 24px;
    width: 360px;
    max-width: calc(100vw - 48px);
    background: rgba(15, 15, 20, 0.85);
    backdrop-filter: blur(24px) saturate(1.5);
    -webkit-backdrop-filter: blur(24px) saturate(1.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 28px 24px 24px;
    z-index: 1000;
    box-shadow:
      0 24px 80px rgba(0, 0, 0, 0.6),
      0 0 0 1px rgba(99, 102, 241, 0.1),
      inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }

  .ap-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    cursor: pointer;
    padding: 6px;
    border-radius: 8px;
    display: flex;
    transition: all 0.15s;
  }
  .ap-close:hover {
    color: white;
    background: rgba(255, 255, 255, 0.08);
  }

  .ap-form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .ap-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: white;
    margin: 0;
    letter-spacing: -0.3px;
  }

  .ap-subtitle {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.5);
    margin: -6px 0 4px;
    line-height: 1.4;
    word-break: break-all;
  }

  .ap-field {
    position: relative;
    display: flex;
    align-items: center;
  }

  .ap-icon {
    position: absolute;
    left: 14px;
    color: rgba(255, 255, 255, 0.3);
    pointer-events: none;
  }

  .ap-input {
    width: 100%;
    padding: 12px 14px 12px 40px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    color: white;
    font-size: 0.95rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
  }
  .ap-input:focus {
    border-color: rgba(99, 102, 241, 0.5);
  }
  .ap-input::placeholder {
    color: rgba(255, 255, 255, 0.25);
  }

  .ap-otp-field .ap-input {
    text-align: center;
    font-size: 1.6rem;
    font-weight: 600;
    letter-spacing: 10px;
    padding-left: 14px;
    font-family: 'JetBrains Mono', monospace;
  }

  .ap-eye {
    position: absolute;
    right: 12px;
    background: transparent;
    border: none;
    color: rgba(255, 255, 255, 0.3);
    cursor: pointer;
    padding: 4px;
    display: flex;
  }
  .ap-eye:hover { color: rgba(255, 255, 255, 0.6); }

  .ap-btn-primary {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 20px;
    background: linear-gradient(135deg, #6366f1, #4f46e5);
    border: none;
    border-radius: 12px;
    color: white;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
    margin-top: 2px;
  }
  .ap-btn-primary:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.35);
  }
  .ap-btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  .ap-link {
    background: none;
    border: none;
    color: rgba(99, 102, 241, 0.8);
    font-size: 0.82rem;
    cursor: pointer;
    font-family: inherit;
    text-align: center;
    padding: 2px;
    transition: color 0.15s;
  }
  .ap-link:hover { color: #818cf8; }

  .ap-back {
    display: flex;
    align-items: center;
    gap: 4px;
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.4);
    font-size: 0.8rem;
    cursor: pointer;
    font-family: inherit;
    padding: 0;
    margin-bottom: -4px;
    align-self: flex-start;
    transition: color 0.15s;
  }
  .ap-back:hover { color: rgba(255, 255, 255, 0.7); }

  .ap-error {
    color: #f87171;
    font-size: 0.82rem;
    text-align: center;
    margin-top: 4px;
    line-height: 1.4;
  }

  .ap-toast {
    color: #34d399;
    font-size: 0.82rem;
    text-align: center;
    margin-top: 4px;
  }

  .ap-success {
    align-items: center;
    padding: 20px 0;
  }
  .ap-success-icon {
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: linear-gradient(135deg, #10b981, #059669);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    margin-bottom: 8px;
  }

  @keyframes ap-spin-anim {
    to { transform: rotate(360deg); }
  }
  .ap-spin {
    animation: ap-spin-anim 0.8s linear infinite;
  }

  @media (max-width: 480px) {
    .ap-panel {
      right: 12px;
      left: 12px;
      width: auto;
      top: 56px;
    }
  }
`;
