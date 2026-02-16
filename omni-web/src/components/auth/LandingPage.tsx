import { FormEvent, useState, useEffect } from "react";

interface LandingPageProps {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string, displayName: string) => Promise<void>;
  isLoading: boolean;
  error: string;
}

interface Star {
  id: number;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
}

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  duration: number;
  delay: number;
  opacity: number;
}

interface ShootingStar {
  id: number;
  delay: number;
}

export function LandingPage({ onLogin, onRegister, isLoading, error }: LandingPageProps) {
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [stars, setStars] = useState<Star[]>([]);
  const [particles, setParticles] = useState<Particle[]>([]);
  const [shootingStars, setShootingStars] = useState<ShootingStar[]>([]);
  
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

  // Initialize animations
  useEffect(() => {
    const newStars = Array.from({ length: 80 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 2 + 1,
      duration: Math.random() * 3 + 2,
      delay: Math.random() * 3,
    }));
    setStars(newStars);

    const newParticles = Array.from({ length: 20 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 4 + 2,
      duration: Math.random() * 15 + 10,
      delay: Math.random() * 10,
      opacity: Math.random() * 0.5 + 0.2,
    }));
    setParticles(newParticles);

    const newShootingStars = Array.from({ length: 3 }, (_, i) => ({
      id: i,
      delay: i * 8 + Math.random() * 4,
    }));
    setShootingStars(newShootingStars);
  }, []);

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

  const switchMode = () => {
    setIsAnimating(true);
    setTimeout(() => {
      setIsRegisterMode(!isRegisterMode);
      setRegError("");
      setIsAnimating(false);
    }, 150);
  };

  const features = [
    { icon: "💬", name: "AI Chat" },
    { icon: "⚡", name: "Workflows" },
    { icon: "🧠", name: "Memory" },
    { icon: "🔌", name: "Tools" },
    { icon: "🔬", name: "Research" },
  ];

  return (
    <div className="landing-page">
      {/* Background Effects */}
      <div className="bg-effects">
        {/* Animated gradient mesh */}
        <div className="gradient-mesh"></div>
        
        {/* Smooth glowing orbs */}
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
        <div className="orb orb-3"></div>
        <div className="orb orb-4"></div>
        
        {/* Grid */}
        <div className="grid-bg"></div>
        
        {/* Floating particles */}
        {particles.map((particle) => (
          <div
            key={particle.id}
            className="particle"
            style={{
              left: `${particle.x}%`,
              top: `${particle.y}%`,
              width: `${particle.size}px`,
              height: `${particle.size}px`,
              animationDuration: `${particle.duration}s`,
              animationDelay: `${particle.delay}s`,
              opacity: particle.opacity,
            }}
          />
        ))}
        
        {/* Stars */}
        {stars.map((star) => (
          <div
            key={star.id}
            className="star"
            style={{
              left: `${star.x}%`,
              top: `${star.y}%`,
              width: `${star.size}px`,
              height: `${star.size}px`,
              animationDuration: `${star.duration}s`,
              animationDelay: `${star.delay}s`,
            }}
          />
        ))}

        {/* Shooting stars */}
        {shootingStars.map((star) => (
          <div
            key={star.id}
            className="shooting-star"
            style={{
              animationDelay: `${star.delay}s`,
            }}
          />
        ))}
      </div>

      <div className="landing-container">
        {/* Logo & Branding */}
        <div className="landing-header">
          <div className="logo-container">
            <div className="logo-glow"></div>
            <div className="logo">
              <img src="/favicon.svg" alt="OmniAI" className="logo-img" />
            </div>
          </div>
          <h1 className="brand-name">
            <span className="gradient-text">OmniAI</span>
          </h1>
          <p className="brand-tagline">Your AI-Powered Workspace</p>
        </div>

        {/* Auth Card */}
        <div className={`auth-card ${isAnimating ? 'animating-out' : 'animating-in'}`}>
          <div className="card-glow"></div>
          <div className="auth-header">
            <h2>{isRegisterMode ? "Create Account" : "Welcome Back"}</h2>
            <p>{isRegisterMode ? "Get started with OmniAI" : "Sign in to continue"}</p>
          </div>

          {isRegisterMode ? (
            <form onSubmit={handleRegisterSubmit} className="auth-form">
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
                    placeholder="Your name"
                    required
                    autoComplete="name"
                  />
                </div>
              </div>

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
                    placeholder="Username"
                    required
                    autoComplete="username"
                  />
                </div>
              </div>

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
                    placeholder="Password"
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

              <div className="input-group">
                <label className="input-label">Confirm Password</label>
                <div className="input-wrapper">
                  <svg className="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  <input
                    type={regShowPassword ? "text" : "password"}
                    className="input auth-input"
                    value={regConfirmPassword}
                    onChange={(e) => setRegConfirmPassword(e.target.value)}
                    placeholder="Confirm password"
                    required
                    autoComplete="new-password"
                  />
                </div>
              </div>

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

              <button type="submit" className="btn btn-primary btn-auth" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <span className="spinner"></span>
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </button>

              <div className="auth-switch">
                <span>Already have an account?</span>
                <button type="button" className="link-btn" onClick={switchMode}>
                  Sign In
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleLoginSubmit} className="auth-form">
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
                    placeholder="Username"
                    required
                    autoComplete="username"
                  />
                </div>
              </div>

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
                    placeholder="Password"
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

              <button type="submit" className="btn btn-primary btn-auth" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <span className="spinner"></span>
                    Signing in...
                  </>
                ) : (
                  "Sign In"
                )}
              </button>

              <div className="auth-switch">
                <span>Don't have an account?</span>
                <button type="button" className="link-btn" onClick={switchMode}>
                  Sign Up
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Features */}
        <div className="features-row">
          {features.map((feature, index) => (
            <div key={index} className="feature-item">
              <span className="feature-icon">{feature.icon}</span>
              <span className="feature-name">{feature.name}</span>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="landing-footer">
          <p>© 2026 OmniAI • Built with modern AI architecture</p>
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
          background: #0d1117;
        }

        /* Background Effects */
        .bg-effects {
          position: absolute;
          inset: 0;
          pointer-events: none;
        }

        /* Animated Gradient Mesh */
        .gradient-mesh {
          position: absolute;
          inset: 0;
          background: 
            radial-gradient(ellipse at 20% 30%, rgba(88, 166, 255, 0.15) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 70%, rgba(188, 140, 255, 0.12) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(247, 120, 186, 0.08) 0%, transparent 60%);
          animation: meshMove 15s ease-in-out infinite;
        }

        @keyframes meshMove {
          0%, 100% { transform: scale(1) rotate(0deg); }
          25% { transform: scale(1.1) rotate(2deg); }
          50% { transform: scale(1) rotate(0deg); }
          75% { transform: scale(1.05) rotate(-2deg); }
        }

        /* Smooth Glowing Orbs */
        .orb {
          position: absolute;
          border-radius: 50%;
          filter: blur(80px);
          opacity: 0.4;
          animation: orbFloat 20s ease-in-out infinite;
        }

        .orb-1 {
          width: 600px;
          height: 600px;
          background: radial-gradient(circle, rgba(88, 166, 255, 0.5) 0%, transparent 70%);
          top: -200px;
          left: -200px;
          animation-delay: 0s;
        }

        .orb-2 {
          width: 500px;
          height: 500px;
          background: radial-gradient(circle, rgba(188, 140, 255, 0.4) 0%, transparent 70%);
          bottom: -150px;
          right: -150px;
          animation-delay: -7s;
        }

        .orb-3 {
          width: 400px;
          height: 400px;
          background: radial-gradient(circle, rgba(63, 185, 80, 0.3) 0%, transparent 70%);
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          animation-delay: -14s;
        }

        .orb-4 {
          width: 300px;
          height: 300px;
          background: radial-gradient(circle, rgba(247, 120, 186, 0.3) 0%, transparent 70%);
          top: 20%;
          right: 10%;
          animation-delay: -5s;
        }

        @keyframes orbFloat {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -30px) scale(1.05); }
          66% { transform: translate(-20px, 20px) scale(0.95); }
        }

        /* Grid */
        .grid-bg {
          position: absolute;
          inset: 0;
          background-image: 
            linear-gradient(rgba(88, 166, 255, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(88, 166, 255, 0.03) 1px, transparent 1px);
          background-size: 50px 50px;
        }

        /* Stars */
        .star {
          position: absolute;
          background: rgba(200, 210, 230, 0.9);
          border-radius: 50%;
          animation: twinkle 3s ease-in-out infinite;
        }

        @keyframes twinkle {
          0%, 100% { opacity: 0.3; transform: scale(0.8); }
          50% { opacity: 1; transform: scale(1.2); }
        }

        /* Floating Particles */
        .particle {
          position: absolute;
          background: radial-gradient(circle, rgba(255, 255, 255, 0.8) 0%, transparent 70%);
          border-radius: 50%;
          animation: particleFloat 15s ease-in-out infinite;
        }

        @keyframes particleFloat {
          0%, 100% { 
            transform: translate(0, 0) scale(1); 
            opacity: var(--base-opacity, 0.3);
          }
          25% { 
            transform: translate(20px, -30px) scale(1.2); 
            opacity: 0.6;
          }
          50% { 
            transform: translate(-10px, -50px) scale(0.8); 
            opacity: 0.4;
          }
          75% { 
            transform: translate(-30px, -20px) scale(1.1); 
            opacity: 0.5;
          }
        }

        /* Shooting Stars */
        .shooting-star {
          position: absolute;
          top: 10%;
          right: 20%;
          width: 100px;
          height: 2px;
          background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.8), rgba(255, 255, 255, 0));
          animation: shootStar 8s ease-in-out infinite;
          opacity: 0;
          transform: rotate(-45deg);
        }

        .shooting-star::after {
          content: '';
          position: absolute;
          top: -2px;
          right: 0;
          width: 6px;
          height: 6px;
          background: white;
          border-radius: 50%;
          box-shadow: 0 0 10px 2px rgba(255, 255, 255, 0.5);
        }

        @keyframes shootStar {
          0%, 90% { 
            opacity: 0;
            transform: translateX(0) rotate(-45deg);
          }
          92% {
            opacity: 1;
          }
          100% { 
            opacity: 0;
            transform: translateX(-500px) translateY(500px) rotate(-45deg);
          }
        }

        /* Container */
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

        /* Header */
        .landing-header {
          text-align: center;
          margin-bottom: var(--space-2XL);
        }

        .logo-container {
          position: relative;
          display: inline-block;
          margin-bottom: var(--space-md);
        }

        .logo-glow {
          position: absolute;
          inset: -20px;
          background: radial-gradient(circle, rgba(88, 166, 255, 0.3) 0%, transparent 70%);
          border-radius: 50%;
          animation: logoGlow 3s ease-in-out infinite;
          filter: blur(10px);
        }

        @keyframes logoGlow {
          0%, 100% { transform: scale(1); opacity: 0.5; }
          50% { transform: scale(1.2); opacity: 0.8; }
        }

        .logo {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          animation: logoFloat 4s ease-in-out infinite;
        }

        @keyframes logoFloat {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }

        .logo-symbol {
          width: 40px;
          height: 40px;
        }

        .logo-img {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          filter: drop-shadow(0 0 20px rgba(88, 166, 255, 0.5));
        }

        .brand-name {
          font-size: 42px;
          font-weight: 800;
          margin: 0 0 var(--space-xs);
          letter-spacing: -1px;
        }

        .gradient-text {
          background: linear-gradient(135deg, #58a6ff 0%, #bc8cff 50%, #f778ba 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: gradientShift 5s ease infinite;
          background-size: 200% 200%;
        }

        @keyframes gradientShift {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }

        .brand-tagline {
          font-size: var(--font-size-md);
          color: var(--text-secondary);
          margin: 0;
        }

        /* Auth Card */
        .auth-card {
          position: relative;
          width: 100%;
          background: rgba(22, 27, 34, 0.85);
          backdrop-filter: blur(20px);
          border: 1px solid rgba(88, 166, 255, 0.15);
          border-radius: 20px;
          padding: var(--space-xl);
          margin-bottom: var(--space-2XL);
          overflow: hidden;
        }

        .card-glow {
          position: absolute;
          inset: -2px;
          background: linear-gradient(135deg, rgba(88, 166, 255, 0.3), rgba(188, 140, 255, 0.2), rgba(247, 120, 186, 0.3));
          border-radius: 22px;
          z-index: -1;
          opacity: 0.5;
          animation: cardGlow 4s ease-in-out infinite;
        }

        @keyframes cardGlow {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 0.6; }
        }

        .auth-card.animating-out {
          animation: cardSlideOut 0.15s ease-in forwards;
        }

        .auth-card.animating-in {
          animation: cardSlideIn 0.15s ease-out forwards;
        }

        @keyframes cardSlideOut {
          to { opacity: 0; transform: translateX(-10px); }
        }

        @keyframes cardSlideIn {
          from { opacity: 0; transform: translateX(10px); }
          to { opacity: 1; transform: translateX(0); }
        }

        .auth-header {
          text-align: center;
          margin-bottom: var(--space-lg);
        }

        .auth-header h2 {
          font-size: 22px;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 var(--space-xs);
        }

        .auth-header p {
          font-size: var(--font-size-sm);
          color: var(--text-secondary);
          margin: 0;
        }

        /* Form */
        .auth-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }

        .input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }

        .input-icon {
          position: absolute;
          left: 12px;
          width: 16px;
          height: 16px;
          color: var(--text-muted);
          pointer-events: none;
          transition: color 0.2s;
        }

        .input-wrapper:focus-within .input-icon {
          color: var(--accent-primary);
        }

        .auth-input {
          padding-left: 38px !important;
          padding-right: 38px !important;
          height: 48px;
          background: rgba(13, 17, 23, 0.8) !important;
          border: 1px solid rgba(88, 166, 255, 0.2) !important;
          border-radius: 10px !important;
          font-size: 14px;
          transition: all 0.2s;
        }

        .auth-input:focus {
          border-color: var(--accent-primary) !important;
          box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15) !important;
          background: rgba(13, 17, 23, 1) !important;
        }

        .auth-input::placeholder {
          color: var(--text-muted);
        }

        .password-toggle {
          position: absolute;
          right: 8px;
          width: 28px;
          height: 28px;
          padding: 0;
          background: transparent;
          border: none;
          cursor: pointer;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 6px;
          transition: all 0.2s;
        }

        .password-toggle:hover {
          color: var(--text-secondary);
          background: rgba(88, 166, 255, 0.15);
        }

        .password-toggle svg {
          width: 16px;
          height: 16px;
        }

        /* Error */
        .auth-error {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-sm) var(--space-md);
          background: rgba(248, 81, 73, 0.1);
          border: 1px solid rgba(248, 81, 73, 0.3);
          border-radius: 10px;
          color: #f85149;
          font-size: var(--font-size-sm);
        }

        .auth-error svg {
          width: 14px;
          height: 14px;
          flex-shrink: 0;
        }

        /* Button */
        .btn-auth {
          height: 48px;
          font-size: 15px;
          font-weight: 600;
          border-radius: 10px;
          background: linear-gradient(135deg, #58a6ff 0%, #bc8cff 100%);
          margin-top: var(--space-sm);
          transition: all 0.3s;
          box-shadow: 0 4px 15px rgba(88, 166, 255, 0.3);
        }

        .btn-auth:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(88, 166, 255, 0.4);
        }

        .btn-auth:active:not(:disabled) {
          transform: translateY(0);
        }

        /* Switch */
        .auth-switch {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-xs);
          color: var(--text-muted);
          font-size: var(--font-size-sm);
          margin-top: var(--space-sm);
        }

        .link-btn {
          background: none;
          border: none;
          color: var(--accent-primary);
          cursor: pointer;
          font-size: var(--font-size-sm);
          padding: 0;
          font-weight: 500;
          transition: all 0.2s;
        }

        .link-btn:hover {
          text-decoration: underline;
          text-shadow: 0 0 10px rgba(88, 166, 255, 0.5);
        }

        /* Features */
        .features-row {
          display: flex;
          gap: var(--space-xl);
          margin-bottom: var(--space-xl);
        }

        .feature-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-xs);
        }

        .feature-icon {
          font-size: 22px;
          transition: transform 0.3s;
        }

        .feature-item:hover .feature-icon {
          transform: scale(1.2);
        }

        .feature-name {
          font-size: var(--font-size-xs);
          color: var(--text-secondary);
        }

        /* Footer */
        .landing-footer {
          margin-top: auto;
        }

        .landing-footer p {
          font-size: var(--font-size-xs);
          color: var(--text-muted);
          margin: 0;
        }

        /* Spinner */
        .spinner {
          width: 16px;
          height: 16px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        /* Responsive */
        @media (max-width: 480px) {
          .features-row {
            gap: var(--space-lg);
          }
          
          .brand-name {
            font-size: 32px;
          }
          
          .logo {
            width: 60px;
            height: 60px;
          }
        }
      `}</style>
    </div>
  );
}
