import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import HybridAnalysisPage from './pages/HybridAnalysisPage'
import ChatPage from './pages/ChatPage'
import Home from './pages/Home'
import Analysis from './pages/Analysis'
import Report from './pages/Report'

function App() {
  return (
    <Router>
      <Routes>
        {/* Streaming analysis interface (default) */}
        <Route path="/" element={<Home />} />
        <Route path="/chat" element={<ChatPage />} />

        {/* Alternative interfaces */}
        <Route path="/hybrid" element={<HybridAnalysisPage />} />

        {/* Legacy routes (kept for reference) */}
        <Route path="/analysis/:id" element={<Analysis />} />
        <Route path="/report/:id" element={<Report />} />
      </Routes>
    </Router>
  )
}

export default App
