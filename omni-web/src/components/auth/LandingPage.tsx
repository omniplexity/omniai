import { FormEvent, useState } from "react";

interface LandingPageProps {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string, displayName: string) => Promise<void>;
  isLoading: boolean;
  error: string;
}

export function LandingPage({ onLogin, onRegister, isLoading, error }: LandingPageProps) {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  
  // Login form state
  const [username, setUsername] = useState("dev-user");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  
  // Register form state
  const [regUsername, setRegUsername] = useState("");
  const [regDisplayName, setRegDisplayName] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");
  const [regShowPassword, setRegShowPassword] = useState(false);
  const [regError, setRegError] = useState("");

  const handleLoginSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await onLogin(username, password);
  };

  const handleRegisterSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setRegError("");
    
    if (regPassword !== regConfirmPassword) {
      setRegError("Passwords do not match");
      return;
    }
    
    if (regPassword.length < 6) {
      setRegError("Password must be at least 6 characters");
      return;
    }
    
    if (!regUsername.trim() || !regDisplayName.trim()) {
      setRegError("Username and display name are required");
      return;
    }
    
    await onRegister(regUsername.trim(), regPassword, regDisplayName.trim());
  };

  const handleDemoLogin = async () => {
    await onLogin("demo", "");
  };

  const switchMode = () => {
    setIsRegisterMode(!isRegisterMode);
    setRegError("");
  };

  return (
    <div className="landing-page">
      {/* Animated Background */}
      <div className="landing-bg">
        <div className="bg-gradient bg-gradient-1"></div>
        <div className="bg-gradient bg-gradient-2"></div>
        <div className="bg-gradient bg-gradient-3"></div>
        <div className="bg-grid"></div>
      </div>

      <div className="landing-container">
        {/* Logo & Branding */}
        <div className="landing-header">
          <div className="logo-container">
            <div className="logo-glow"></div>
            <div className="logo-icon">O</div>
          </div>
          <h1 className="brand-name">OmniAI</h1>
          <p className="brand-tagline">Your AI-Powered Workspace</p>
        </div>

        {/* Auth Card */}
        <div className="auth-card">
          <div className="auth-header">
            <h2>{isRegisterMode ? "Create Account" : "Welcome Back"}</h2>
            <p>{isRegisterMode ? "Sign up to start your AI workspace" : "Sign in to continue to your workspace"}</p>
          </div>

          {isRegisterMode ? (
            /* Registration Form */
            <form onSubmit={handleRegisterSubmit} className="auth-form">
              {/* Display Name Input */}
              <div className="input-group">
                <label className="input-label">Display Name</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  <input
                    type="text"
                    className="input auth-input"
                    value={regDisplayName}
                    onChange={(e) => setRegDisplayName(e.target.value)}
                    placeholder="Your display name"
                    required
                    autoComplete="name"
                  />
                </div>
              </div>

              {/* Username Input */}
              <div className="input-group">
                <label className="input-label">Username</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  <input
                    type="text"
                    className="input auth-input"
                    value={regUsername}
                    onChange={(e) => setRegUsername(e.target.value)}
                    placeholder="Choose a username"
                    required
                    autoComplete="username"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="input-group">
                <label className="input-label">Password</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <input
                    type={regShowPassword ? "text" : "password"}
                    className="input auth-input"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder="Create a password"
                    required
                    autoComplete="new-password"
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setRegShowPassword(!regShowPassword)}
                  >
                    {regShowPassword ? (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.06 3.94m-6.72-1.72a3 3 0 0 0-4.12-4.12" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 4 8 11-8 11 8-4 8-11 8-4-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Confirm Password Input */}
              <div className="input-group">
                <label className="input-label">Confirm Password</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <input
                    type={regShowPassword ? "text" : "password"}
                    className="input auth-input"
                    value={regConfirmPassword}
                    onChange={(e) => setRegConfirmPassword(e.target.value)}
                    placeholder="Confirm your password"
                    required
                    autoComplete="new-password"
                  />
                </div>
              </div>

              {/* Error Message */}
              {(error || regError) && (
                <div className="auth-error">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{error || regError}</span>
                </div>
              )}

              {/* Submit Button */}
              <button type="submit" className="btn btn-primary btn-auth" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <span className="spinner"></span>
                    Creating account...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                      <circle cx="8.5" cy="7" r="4" />
                      <line x1="20" y1="8" x2="20" y2="14" />
                      <line x1="23" y1="11" x2="17" y2="11" />
                    </svg>
                    Create Account
                  </>
                )}
              </button>

              {/* Switch to Login */}
              <div className="auth-switch">
                <span>Already have an account?</span>
                <button type="button" className="link-btn" onClick={switchMode}>
                  Sign In
                </button>
              </div>
            </form>
          ) : (
            /* Login Form */
            <form onSubmit={handleLoginSubmit} className="auth-form">
              {/* Username Input */}
              <div className="input-group">
                <label className="input-label">Username</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                  <input
                    type="text"
                    className="input auth-input"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter your username"
                    required
                    autoComplete="username"
                  />
                </div>
              </div>

              {/* Password Input */}
              <div className="input-group">
                <label className="input-label">Password</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                  </svg>
                  <input
                    type={showPassword ? "text" : "password"}
                    className="input auth-input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password (optional for demo)"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.06 3.94m-6.72-1.72a3 3 0 0 0-4.12-4.12" />
                        <line x1="1" y1="1" x2="23" y2="23" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M1 12s4-8 11-8 11 8 4 8 11-8 11 8-4 8-11 8-4-8-11-8z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="auth-error">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="12" y1="8" x2="12" y2="12" />
                    <line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                  <span>{error}</span>
                </div>
              )}

              {/* Submit Button */}
              <button type="submit" className="btn btn-primary btn-auth" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <span className="spinner"></span>
                    Signing in...
                  </>
                ) : (
                  <>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                      <polyline points="10 17 15 12 10 21" />
                      <line x1="4" y1="12" x2="20" y2="12" />
                    </svg>
                    Sign In
                  </>
                )}
              </button>

              {/* Divider */}
              <div className="auth-divider">
                <span>or</span>
              </div>

              {/* Demo Button */}
              <button type="button" className="btn btn-secondary btn-demo" onClick={handleDemoLogin} disabled={isLoading}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Try Demo Mode
              </button>

              {/* Switch to Register */}
              <div className="auth-switch">
                <span>Don't have an account?</span>
                <button type="button" className="link-btn" onClick={switchMode}>
                  Sign Up
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Features Preview */}
        <div className="features-preview">
          <div className="feature-item">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <span>AI Chat</span>
          </div>
          <div className="feature-item">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <line x1="3" y1="9" x2="21" y2="9" />
                <line x1="9" y1="21" x2="9" y2="9" />
              </svg>
            </div>
            <span>Workflows</span>
          </div>
          <div className="feature-item">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3v18M3 12h18" />
              </svg>
            </div>
            <span>Memory</span>
          </div>
          <div className="feature-item">
            <div className="feature-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <span>Tools</span>
          </div>
        </div>

        {/* Footer */}
        <div className="landing-footer">
          <p>© 2026 OmniAI. Built with modern AI architecture.</p>
        </div>
      </div>

      <style>{`
        .landing-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          overflow: hidden;
          background: var(--bg-primary);
        }

        .landing-bg {
          position: absolute;
          inset: 0;
          overflow: hidden;
        }

        .bg-gradient {
          position: absolute;
          border-radius: 50%;
          filter: blur(100px);
          opacity: 0.4;
          animation: float 20s ease-in-out infinite;
        }

        .bg-gradient-1 {
          width: 600px;
          height: 600px;
          background: radial-gradient(circle, var(--accent-primary) 0%, transparent 70%);
          top: -200px;
          left: -100px;
          animation-delay: 0s;
        }

        .bg-gradient-2 {
          width: 500px;
          height: 500px;
          background: radial-gradient(circle, var(--accent-secondary) 0%, transparent 70%);
          bottom: -150px;
          right: -100px;
          animation-delay: -7s;
        }

        .bg-gradient-3 {
          width: 400px;
          height: 400px;
          background: radial-gradient(circle, var(--accent-tertiary) 0%, transparent 70%);
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          animation-delay: -14s;
        }

        @keyframes float {
          0%, 100% { transform: translate(0, 0) scale(1); }
          25% { transform: translate(30px, -30px) scale(1.05); }
          50% { transform: translate(-20px, 20px) scale(0.95); }
          75% { transform: translate(20px, 30px) scale(1.02); }
        }

        .bg-grid {
          position: absolute;
          inset: 0;
          background-image: 
            linear-gradient(rgba(88, 166, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(88, 166, 255, 0.03) 1px, transparent 1px);
          background-size: 50px 50px;
          mask-image: radial-gradient(ellipse at center, black 30%, transparent 70%);
        }

        .landing-container {
          position: relative;
          z-index: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: var(--space-xl);
          max-width: 420px;
          width: 100%;
        }

        .landing-header {
          text-align: center;
          margin-bottom: var(--space-2xl);
          animation: fadeInUp 0.8s ease-out;
        }

        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .logo-container {
          position: relative;
          display: inline-block;
          margin-bottom: var(--space-lg);
        }

        .logo-glow {
          position: absolute;
          inset: -20px;
          background: radial-gradient(circle, var(--accent-primary) 0%, transparent 70%);
          opacity: 0.5;
          animation: pulseGlow 2s ease-in-out infinite;
        }

        @keyframes pulseGlow {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.1); }
        }

        .logo-icon {
          position: relative;
          width: 80px;
          height: 80px;
          background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
          border-radius: var(--radius-xl);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          font-weight: 700;
          color: white;
          box-shadow: 0 0 40px rgba(88, 166, 255, 0.4);
        }

        .brand-name {
          font-size: 36px;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 var(--space-xs);
          background: linear-gradient(135deg, var(--text-primary), var(--accent-primary));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .brand-tagline {
          font-size: var(--font-size-lg);
          color: var(--text-secondary);
          margin: 0;
        }

        .auth-card {
          width: 100%;
          background: rgba(22, 27, 34, 0.8);
          backdrop-filter: blur(20px);
          border: 1px solid var(--border-default);
          border-radius: var(--radius-xl);
          padding: var(--space-xl);
          animation: fadeInUp 0.8s ease-out 0.2s both;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        }

        .auth-header {
          text-align: center;
          margin-bottom: var(--space-xl);
        }

        .auth-header h2 {
          font-size: var(--font-size-xl);
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 var(--space-xs);
        }

        .auth-header p {
          font-size: var(--font-size-sm);
          color: var(--text-secondary);
          margin: 0;
        }

        .auth-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-lg);
        }

        .input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .input-icon {
          position: absolute;
          left: 14px;
          width: 18px;
          height: 18px;
          color: var(--text-muted);
          pointer-events: none;
        }

        .auth-input {
          padding-left: 44px !important;
          padding-right: 44px !important;
          height: 48px;
          background: var(--bg-primary) !important;
          border: 1px solid var(--border-default) !important;
          transition: all var(--transition-fast) !important;
        }

        .auth-input:focus {
          border-color: var(--accent-primary) !important;
          box-shadow: 0 0 0 3px var(--accent-primary-muted) !important;
        }

        .password-toggle {
          position: absolute;
          right: 12px;
          width: 24px;
          height: 24px;
          padding: 0;
          background: transparent;
          border: none;
          cursor: pointer;
          color: var(--text-muted);
          transition: color var(--transition-fast);
        }

        .password-toggle:hover {
          color: var(--text-secondary);
        }

        .password-toggle svg {
          width: 100%;
          height: 100%;
        }

        .auth-error {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-sm) var(--space-md);
          background: var(--error-muted);
          border: 1px solid var(--error);
          border-radius: var(--radius-md);
          color: var(--error);
          font-size: var(--font-size-sm);
          animation: shake 0.5s ease-in-out;
        }

        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-5px); }
          75% { transform: translateX(5px); }
        }

        .auth-error svg {
          width: 16px;
          height: 16px;
          flex-shrink: 0;
        }

        .btn-auth {
          height: 48px;
          font-size: var(--font-size-md);
          font-weight: 600;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
        }

        .btn-auth svg {
          width: 18px;
          height: 18px;
        }

        .auth-divider {
          display: flex;
          align-items: center;
          gap: var(--space-md);
          color: var(--text-muted);
          font-size: var(--font-size-sm);
        }

        .auth-divider::before,
        .auth-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: var(--border-default);
        }

        .btn-demo {
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
          background: transparent;
          border: 1px solid var(--border-default);
        }

        .btn-demo:hover {
          background: var(--bg-elevated);
          border-color: var(--accent-primary);
        }

        .btn-demo svg {
          width: 16px;
          height: 16px;
        }

        .auth-switch {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
          color: var(--text-muted);
          font-size: var(--font-size-sm);
        }

        .link-btn {
          background: none;
          border: none;
          color: var(--accent-primary);
          cursor: pointer;
          font-size: var(--font-size-sm);
          padding: 0;
          transition: color var(--transition-fast);
        }

        .link-btn:hover {
          color: var(--accent-secondary);
          text-decoration: underline;
        }

        .features-preview {
          display: flex;
          gap: var(--space-xl);
          margin-top: var(--space-2xl);
          animation: fadeInUp 0.8s ease-out 0.4s both;
        }

        .feature-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-sm);
          color: var(--text-muted);
          font-size: var(--font-size-xs);
          transition: color var(--transition-fast);
        }

        .feature-item:hover {
          color: var(--accent-primary);
        }

        .feature-icon {
          width: 32px;
          height: 32px;
          padding: 6px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-default);
          border-radius: var(--radius-md);
          transition: all var(--transition-fast);
        }

        .feature-item:hover .feature-icon {
          background: var(--accent-primary-muted);
          border-color: var(--accent-primary);
        }

        .feature-icon svg {
          width: 100%;
          height: 100%;
        }

        .landing-footer {
          margin-top: var(--space-2xl);
          animation: fadeInUp 0.8s ease-out 0.6s both;
        }

        .landing-footer p {
          font-size: var(--font-size-xs);
          color: var(--text-muted);
          margin: 0;
        }

        @media (max-width: 480px) {
          .landing-container {
            padding: var(--space-lg);
          }
          
          .features-preview {
            gap: var(--space-lg);
          }
          
          .brand-name {
            font-size: 28px;
          }
          
          .logo-icon {
            width: 64px;
            height: 64px;
            font-size: 24px;
          }
        }
      `}</style>
    </div>
  );
}
