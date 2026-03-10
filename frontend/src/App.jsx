import { useState, useCallback } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import AppShell from "./components/AppShell";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import WhatsAppBotPage from "./pages/WhatsAppBotPage";
import SettingsPage from "./pages/SettingsPage";
import { getAccessToken, clearAccessToken } from "./services/auth";

// Auth context via simple prop drilling — no external lib needed
function ProtectedRoute({ isAuthed, children }) {
  if (!isAuthed) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const [isAuthed, setIsAuthed] = useState(() => !!getAccessToken());

  const handleLogin = useCallback(() => {
    setIsAuthed(true);
  }, []);

  const handleLogout = useCallback(() => {
    clearAccessToken();
    setIsAuthed(false);
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
      <Route path="/register" element={<RegisterPage onLogin={handleLogin} />} />

      <Route
        element={
          <ProtectedRoute isAuthed={isAuthed}>
            <AppShell onLogout={handleLogout} />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<WhatsAppBotPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
