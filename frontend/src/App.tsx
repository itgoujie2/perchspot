import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import UserMenu from './components/UserMenu'
import StructuredData from './components/StructuredData'
import PageTracker from './components/PageTracker'
import ExitIntentPopup from './components/ExitIntentPopup'
import HybridAnalysisPage from './pages/HybridAnalysisPage'
import ChatPage from './pages/ChatPage'
import Home from './pages/Home'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import Analysis from './pages/Analysis'
import Report from './pages/Report'
import KnowledgeManagement from './pages/KnowledgeManagement'
import AdminPortal from './pages/AdminPortal'
import CreditsPage from './pages/CreditsPage'
import AccountPage from './pages/AccountPage'
import ComparePage from './pages/ComparePage'
import BlogPage from './pages/BlogPage'

function App() {
  return (
    <HelmetProvider>
      <AuthProvider>
        <StructuredData data={{
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "Perchspot",
          "url": "https://perchspot.com",
          "logo": "https://perchspot.com/logo.svg",
          "description": "AI-powered property analysis platform",
          "sameAs": []
        }} />
        <Router>
          <PageTracker />
          <ExitIntentPopup />
          <UserMenu />
          <Routes>
            {/* Auth routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected routes */}
            <Route path="/" element={<Home />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/hybrid" element={<ProtectedRoute><HybridAnalysisPage /></ProtectedRoute>} />
            {/* Admin routes - use their own password auth */}
            <Route path="/knowledge" element={<KnowledgeManagement />} />
            <Route path="/admin" element={<AdminPortal />} />
            <Route path="/credits" element={<ProtectedRoute><CreditsPage /></ProtectedRoute>} />
            <Route path="/account" element={<ProtectedRoute><AccountPage /></ProtectedRoute>} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/blog" element={<BlogPage />} />
            <Route path="/blog/:postId" element={<BlogPage />} />

            {/* Redirects for old routes */}
            <Route path="/favorites" element={<Navigate to="/account?tab=favorites" replace />} />
            <Route path="/history" element={<Navigate to="/account?tab=history" replace />} />

            {/* Legacy routes */}
            <Route path="/analysis/:id" element={<ProtectedRoute><Analysis /></ProtectedRoute>} />
            <Route path="/report/:id" element={<ProtectedRoute><Report /></ProtectedRoute>} />
          </Routes>
        </Router>
      </AuthProvider>
    </HelmetProvider>
  )
}

export default App
