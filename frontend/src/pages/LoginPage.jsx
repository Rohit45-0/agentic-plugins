import { useState, useEffect } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { login } from "../services/auth";
import { Zap, Eye, EyeOff, Loader2 } from "lucide-react";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Handle Google OAuth callback — token comes via URL query param
  useEffect(() => {
    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("cn_access_token", token);
      onLogin?.();
      navigate("/dashboard");
    }

    // Handle error redirects from Google OAuth
    const errParam = searchParams.get("error");
    if (errParam === "AccountNotFound") {
      setError("This Google account is not registered. Please sign up first.");
    } else if (errParam) {
      setError("Google authentication failed. Please try again.");
    }
  }, [searchParams, onLogin, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      onLogin?.();
      navigate("/dashboard");
    } catch (err) {
      // Show the actual backend error message
      const msg = err.message || "Login failed. Check your credentials.";
      setError(msg);
      console.error("Login error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 justify-center mb-8">
          <div className="w-9 h-9 bg-neutral-900 rounded-xl flex items-center justify-center">
            <Zap size={18} className="text-white" strokeWidth={2.5} />
          </div>
          <span className="text-lg font-bold text-neutral-900 tracking-tight">Catalyst Nexus</span>
        </div>

        {/* Card */}
        <div className="bg-white border border-neutral-200 rounded-2xl p-8 shadow-card">
          <h1 className="text-xl font-semibold text-neutral-900 mb-1">Welcome back</h1>
          <p className="text-sm text-neutral-500 mb-6">Sign in to your account</p>

          {error && (
            <div className="mb-4 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-neutral-700 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                className="cn-input"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-neutral-700 mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="cn-input pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-700"
                >
                  {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary justify-center py-2.5 rounded-lg"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : "Sign in"}
            </button>

            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-neutral-200"></div>
              <span className="flex-shrink-0 mx-4 text-neutral-400 text-xs text-center">or</span>
              <div className="flex-grow border-t border-neutral-200"></div>
            </div>

            <button
              type="button"
              onClick={() => {
                const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
                const fallback = window.location.origin;
                window.location.href = `${apiBaseUrl}/auth/google/login?fallback=${encodeURIComponent(fallback)}`;
              }}
              className="w-full flex items-center justify-center gap-3 py-2.5 rounded-lg border border-neutral-200 text-sm font-medium text-neutral-700 bg-white hover:bg-neutral-50 transition-colors shadow-sm"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="18px" height="18px">
                <path fill="#FFC107" d="M43.611,20.083H42V20H24v8h11.303c-1.649,4.657-6.08,8-11.303,8c-6.627,0-12-5.373-12-12c0-6.627,5.373-12,12-12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C12.955,4,4,12.955,4,24c0,11.045,8.955,20,20,20c11.045,0,20-8.955,20-20C44,22.659,43.862,21.35,43.611,20.083z" />
                <path fill="#FF3D00" d="M6.306,14.691l6.571,4.819C14.655,15.108,18.961,12,24,12c3.059,0,5.842,1.154,7.961,3.039l5.657-5.657C34.046,6.053,29.268,4,24,4C16.318,4,9.656,8.337,6.306,14.691z" />
                <path fill="#4CAF50" d="M24,44c5.166,0,9.86-1.977,13.409-5.192l-6.19-5.238C29.211,35.091,26.715,36,24,36c-5.202,0-9.619-3.317-11.283-7.946l-6.522,5.025C9.505,39.556,16.227,44,24,44z" />
                <path fill="#1976D2" d="M43.611,20.083H42V20H24v8h11.303c-0.792,2.237-2.231,4.166-4.087,5.571c0.001-0.001,0.002-0.001,0.003-0.002l6.19,5.238C36.971,39.205,44,34,44,24C44,22.659,43.862,21.35,43.611,20.083z" />
              </svg>
              Continue with Google
            </button>
          </form>

          <p className="text-center text-sm text-neutral-500 mt-5">
            Don't have an account?{" "}
            <Link to="/register" className="text-neutral-900 font-medium hover:underline">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
