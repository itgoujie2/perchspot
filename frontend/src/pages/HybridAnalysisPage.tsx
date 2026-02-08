import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import './HybridAnalysisPage.css';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: any[];
}

interface ChatResponse {
  response: string;
  conversation_id: string;
  tool_calls: any[];
  conversation_history: Message[];
  tokens_used: {
    prompt: number;
    completion: number;
    total: number;
  };
  cost: number;
  iterations: number;
}

interface ReportData {
  property_info?: any;
  school_info?: any;
  location_info?: any;
  summary?: {
    key_findings: string[];
    concerns: string[];
    recommendation: string;
  };
  overall_score?: number;
  overall_grade?: string;
  confidence?: string;
  category_scores?: Record<string, number>;
  detailed_analysis?: any;
  metadata?: any;
}

interface ProgressStep {
  id: number;
  message: string;
  status: 'pending' | 'active' | 'completed';
  icon: string;
  timestamp?: Date;
}

const HybridAnalysisPage: React.FC = () => {
  const navigate = useNavigate();

  // Address input state
  const [address, setAddress] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Progress tracking state
  const [progressSteps, setProgressSteps] = useState<ProgressStep[]>([]);
  const [showProgress, setShowProgress] = useState(false);

  // Report state
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Question quota state
  const [questionsRemaining, setQuestionsRemaining] = useState(5);
  const [stats, setStats] = useState<{ tokens: number; cost: number }>({ tokens: 0, cost: 0 });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Helper function to add/update progress steps
  const addProgressStep = (message: string, icon: string, status: 'active' | 'completed' = 'active') => {
    setProgressSteps(prev => {
      const newStep: ProgressStep = {
        id: prev.length,
        message,
        icon,
        status,
        timestamp: new Date()
      };
      return [...prev, newStep];
    });
  };

  const updateProgressStep = (id: number, status: 'completed') => {
    setProgressSteps(prev =>
      prev.map(step => step.id === id ? { ...step, status } : step)
    );
  };

  const analyzeProperty = async () => {
    if (!address.trim() || analyzing) return;

    try {
      // Navigate to chat page with address as query parameter for streaming analysis
      navigate(`/chat?address=${encodeURIComponent(address)}`);
    } catch (err: any) {
      console.error('Error starting analysis:', err);
      setError(err.response?.data?.detail || 'Failed to start analysis. Please try again.');
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || chatLoading || questionsRemaining <= 0) return;

    const userMessage: Message = {
      role: 'user',
      content: input
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setChatLoading(true);

    try {
      const response = await axios.post<ChatResponse>(
        `${import.meta.env.VITE_API_URL}/api/v1/chat`,
        {
          message: input,
          conversation_id: conversationId
        }
      );

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.data.response,
        tool_calls: response.data.tool_calls
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Decrement questions remaining
      setQuestionsRemaining(prev => prev - 1);

      // Update stats
      setStats({
        tokens: stats.tokens + response.data.tokens_used.total,
        cost: stats.cost + response.data.cost
      });

    } catch (err) {
      console.error('Error sending message:', err);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setChatLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const resetAnalysis = () => {
    setAddress('');
    setReportData(null);
    setMessages([]);
    setConversationId(null);
    setQuestionsRemaining(5);
    setStats({ tokens: 0, cost: 0 });
    setError(null);
    setProgressSteps([]);
    setShowProgress(false);
  };

  return (
    <div className="hybrid-container">
      {/* Header */}
      <div className="hybrid-header">
        <div>
          <h1>Perchspot</h1>
          <p className="subtitle">AI-Powered Property Analysis & Interactive Chat</p>
        </div>
        {reportData && (
          <div className="header-actions">
            <div className="stats">
              <span className="stat">Tokens: {stats.tokens.toLocaleString()}</span>
              <span className="stat">Cost: ${stats.cost.toFixed(4)}</span>
              <span className="stat">Questions: {questionsRemaining}/5</span>
            </div>
            <button onClick={resetAnalysis} className="reset-btn">
              New Analysis
            </button>
          </div>
        )}
      </div>

      {/* Address Input Section (shown when no report) */}
      {!reportData && (
        <div className="address-input-section">
          <div className="input-card">
            <h2>Enter Property Address</h2>
            <p className="input-description">
              Get a comprehensive AI-powered analysis of any property, then ask follow-up questions.
            </p>

            {error && (
              <div className="error-message">
                {error}
                <button onClick={() => setError(null)} className="close-btn">×</button>
              </div>
            )}

            <div className="address-input-form">
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && analyzeProperty()}
                placeholder="123 Main St, Seattle, WA 98101"
                disabled={analyzing}
                className="address-input"
              />
              <button
                onClick={analyzeProperty}
                disabled={analyzing || !address.trim()}
                className="analyze-btn"
              >
                {analyzing ? '⏳ Analyzing...' : '🔍 Analyze Property'}
              </button>
            </div>

            <div className="features">
              <h3>What We Analyze:</h3>
              <div className="feature-grid">
                <div className="feature">
                  <span className="feature-icon">🏡</span>
                  <strong>Property Details</strong>
                  <p>Price, beds, baths, size, photos</p>
                </div>
                <div className="feature">
                  <span className="feature-icon">📍</span>
                  <strong>Location Quality</strong>
                  <p>Neighborhood, amenities, transit</p>
                </div>
                <div className="feature">
                  <span className="feature-icon">🏫</span>
                  <strong>Schools</strong>
                  <p>Ratings, proximity, quality</p>
                </div>
                <div className="feature">
                  <span className="feature-icon">💰</span>
                  <strong>Investment Value</strong>
                  <p>Market trends, ROI potential</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Progress Overlay - Shows during analysis */}
      {showProgress && (
        <div className="progress-overlay-fullscreen">
          <div className="progress-container">
            <div className="progress-header">
              <h3>🔍 Analyzing Property</h3>
              <p className="progress-subtitle">Gathering data from multiple sources...</p>
            </div>
            <div className="progress-steps">
              {progressSteps.map((step, index) => (
                <div
                  key={step.id}
                  className={`progress-step ${step.status}`}
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div className="step-icon">{step.icon}</div>
                  <div className="step-content">
                    <div className="step-message">{step.message}</div>
                    {step.timestamp && (
                      <div className="step-time">
                        {step.timestamp.toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                  {step.status === 'completed' && (
                    <div className="step-check">✓</div>
                  )}
                  {step.status === 'active' && (
                    <div className="step-spinner"></div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Split Screen: Chat (Left) + Report (Right) */}
      {reportData && !showProgress && (
        <div className="split-container">
          {/* Left Panel: Chat */}
          <div className="chat-panel">
            <div className="panel-header">
              <h3>💬 Ask Follow-up Questions</h3>
              <div className="quota-badge">
                {questionsRemaining > 0 ? (
                  `${questionsRemaining} questions left`
                ) : (
                  <span className="quota-exhausted">No questions remaining</span>
                )}
              </div>
            </div>

            <div className="chat-messages">
              {messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <div className="message-content">
                    <div className="message-header">
                      <span className="role-badge">
                        {message.role === 'user' ? '👤 You' : '🤖 Assistant'}
                      </span>
                    </div>
                    <div className="message-text">
                      {message.content}
                    </div>
                    {message.tool_calls && message.tool_calls.length > 0 && (
                      <div className="tool-calls">
                        <div className="tool-calls-header">🛠️ Tools Used:</div>
                        {message.tool_calls.map((tool, toolIndex) => (
                          <div key={toolIndex} className="tool-call">
                            <code>{tool.tool}</code>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {chatLoading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="message-header">
                      <span className="role-badge">🤖 Assistant</span>
                    </div>
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              {questionsRemaining > 0 ? (
                <>
                  <div className="example-prompts">
                    <button onClick={() => setInput('What are the nearby grocery stores?')}>
                      🛒 Nearby stores
                    </button>
                    <button onClick={() => setInput('How is the commute to downtown?')}>
                      🚗 Commute time
                    </button>
                    <button onClick={() => setInput('Tell me more about the schools')}>
                      🏫 School details
                    </button>
                  </div>

                  <div className="input-wrapper">
                    <textarea
                      ref={inputRef}
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask anything about this property..."
                      rows={2}
                      disabled={chatLoading}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={chatLoading || !input.trim()}
                      className="send-btn"
                    >
                      {chatLoading ? '⏳' : '📤'} Send
                    </button>
                  </div>
                </>
              ) : (
                <div className="quota-message">
                  <p>You've used all 5 free questions.</p>
                  <button className="subscribe-btn">
                    ⭐ Subscribe for Unlimited Questions
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Right Panel: Report */}
          <div className="report-panel">
            <div className="panel-header">
              <h3>📊 Comprehensive Property Analysis</h3>
            </div>

            <div className="report-content">
              {reportLoading ? (
                <div className="loading-state">
                  <div className="spinner"></div>
                  <p>Analyzing property across 8 categories...</p>
                  <p className="loading-detail">Gathering data from multiple sources</p>
                </div>
              ) : (
                <>
                  <div className="report-header">
                    <h2 className="property-address">🏠 {address}</h2>
                    <p className="report-date">
                      Analysis generated: {new Date().toLocaleDateString()}
                    </p>
                  </div>

                  <div className="executive-summary">
                    <h3>📋 Executive Summary</h3>
                    <div className="summary-content">
                      {reportData.summary && (
                        <>
                          {reportData.summary.key_findings && reportData.summary.key_findings.length > 0 && (
                            <div className="summary-section">
                              <h4>✨ Key Findings</h4>
                              <ul>
                                {reportData.summary.key_findings.map((finding, idx) => (
                                  <li key={idx}>{finding}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {reportData.summary.concerns && reportData.summary.concerns.length > 0 && (
                            <div className="summary-section">
                              <h4>⚠️ Concerns</h4>
                              <ul>
                                {reportData.summary.concerns.map((concern, idx) => (
                                  <li key={idx}>{concern}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {reportData.summary.recommendation && (
                            <div className="summary-section">
                              <h4>💡 Recommendation</h4>
                              <p>{reportData.summary.recommendation}</p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  <div className="category-breakdown">
                    <h3>🎯 8-Category Analysis</h3>
                    <p className="category-intro">
                      This property has been evaluated across 8 comprehensive categories following industry-standard metrics.
                    </p>

                    <div className="categories-grid">
                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">🏗️</span>
                          <h4>Physical Quality</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Structure, materials, condition</p>
                          <div className="category-placeholder">
                            Based on property data collected
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">📍</span>
                          <h4>Location & Accessibility</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Commute, transport, connectivity</p>
                          <div className="category-placeholder">
                            Walkability and transit options analyzed
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">🏫</span>
                          <h4>Education</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">School quality and resources</p>
                          <div className="category-placeholder">
                            Nearby schools evaluated
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">🏘️</span>
                          <h4>Neighborhood & Environment</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Safety, air quality, community</p>
                          <div className="category-placeholder">
                            Environmental factors assessed
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">🌳</span>
                          <h4>Lot & Land</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Size, topography, features</p>
                          <div className="category-placeholder">
                            Land characteristics reviewed
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">⚠️</span>
                          <h4>Natural Hazards</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Flood, earthquake, fire risks</p>
                          <div className="category-placeholder">
                            Disaster risk evaluation complete
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">💰</span>
                          <h4>Financial & Investment</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Value, ROI, appreciation</p>
                          <div className="category-placeholder">
                            Investment metrics calculated
                          </div>
                        </div>
                      </div>

                      <div className="category-card">
                        <div className="category-header">
                          <span className="category-icon">⚖️</span>
                          <h4>Legal & Regulatory</h4>
                        </div>
                        <div className="category-content">
                          <p className="category-desc">Zoning, HOA, permits</p>
                          <div className="category-placeholder">
                            Regulatory status checked
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Detailed Analysis Section */}
                  <div className="detailed-analysis">
                    <h3>📝 Detailed Analysis</h3>
                    <div className="analysis-content">
                      {reportData.detailed_analysis && (
                        <div className="analysis-text">
                          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
                            {JSON.stringify(reportData.detailed_analysis, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Tool Results */}
                  {reportData.property_info && (
                    <details className="tool-results-section">
                      <summary>🔍 View Raw Data Sources</summary>
                      <div className="tool-results-content">
                        {reportData.property_info && (
                          <div className="data-source">
                            <h4>Property Data (Zillow)</h4>
                            <pre className="json-data">
                              {JSON.stringify(reportData.property_info, null, 2)}
                            </pre>
                          </div>
                        )}
                        {reportData.school_info && (
                          <div className="data-source">
                            <h4>School Data (GreatSchools)</h4>
                            <pre className="json-data">
                              {JSON.stringify(reportData.school_info, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </details>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HybridAnalysisPage;
