import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '../contexts/AuthContext';
import Logo from '../assets/logo.svg';
import DocumentUpload from '../components/DocumentUpload';
import SEOHead from '../components/SEOHead';
import ShareButtons from '../components/ShareButtons';
import ReferralPrompt from '../components/ReferralPrompt';
import { favoritesApi } from '../services/api';
import type { DocumentStatusResponse } from '../types';
import './ChatPage.css';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'status' | 'data' | 'analysis' | 'summary' | 'error';
  step?: number;
  step_name?: string;
}

interface ExtractedStep {
  step: number;
  step_name: string;
  data: Record<string, any>;
  timestamp: string;
}

interface MatchedCondition {
  attribute: string;
  operator: string;
  value: any;
  actual_value: any;
}

interface GenericKnowledgePoint {
  text: string;
  category: string;
  priority: string;
  matched_conditions: MatchedCondition[];
}

// Helper to safely get nested values
const get = (obj: any, path: string, fallback: any = undefined) => {
  return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : fallback), obj);
};

// Build report data from extracted steps
const buildReportData = (steps: ExtractedStep[], finalData: Record<string, any> | null) => {
  const source = finalData || {};
  const stepMap: Record<number, any> = {};
  steps.forEach(s => { stepMap[s.step] = s.data; });

  // Merge property + details from finalData for a combined property view
  const finalProperty = source.property || source.details
    ? { ...(source.property || {}), ...(source.details || {}) }
    : null;

  // Schools: step 4 sends {schools: [...]}, finalData has top-level schools array
  const schoolsRaw = source.schools || stepMap[4];
  const schools = schoolsRaw
    ? (Array.isArray(schoolsRaw) ? schoolsRaw : schoolsRaw.schools || schoolsRaw)
    : null;

  return {
    screenshots: stepMap[1] || null,
    property: finalProperty || stepMap[2] || null,
    pricing: source.pricing || stepMap[3] || null,
    schools,
    location: source.location || stepMap[5] || null,
    climate: source.climate_risks || stepMap[6] || null,
    images: source.images || null,
    propertyAnalysis: stepMap[7] || null,
    locationAnalysis: stepMap[8] || null,
    schoolAnalysis: stepMap[9] || null,
    investmentAnalysis: stepMap[10] || null,
    salePriceAnalysis: stepMap[12] || null,
  };
};

const formatPrice = (n: any) => {
  if (!n) return '—';
  const num = typeof n === 'string' ? parseFloat(n.replace(/[^0-9.]/g, '')) : n;
  if (isNaN(num)) return String(n);
  return '$' + num.toLocaleString();
};

const getGrade = (score: number | null): string | null => {
  if (score === null) return null;
  if (score >= 90) return 'A';
  if (score >= 80) return 'B';
  if (score >= 70) return 'C';
  if (score >= 60) return 'D';
  return 'F';
};

const getRiskColor = (level: string) => {
  const l = (level || '').toLowerCase();
  if (l.includes('low') || l.includes('minimal') || l.includes('none')) return '#4caf50';
  if (l.includes('moderate') || l.includes('medium')) return '#ff9800';
  return '#f44336';
};

// Circular score indicator
const ScoreCircle: React.FC<{ value: number; label: string; max?: number }> = ({ value, label, max = 100 }) => {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const r = 30;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <div className="score-circle">
      <svg width="76" height="76" viewBox="0 0 76 76">
        <circle cx="38" cy="38" r={r} fill="none" stroke="#e0e0e0" strokeWidth="6" />
        <circle cx="38" cy="38" r={r} fill="none" stroke="#667eea" strokeWidth="6"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 38 38)" />
        <text x="38" y="42" textAnchor="middle" fontSize="14" fontWeight="600" fill="#333">{value}</text>
      </svg>
      <span className="score-label">{label}</span>
    </div>
  );
};

// Score bar for analysis sections
const ScoreBar: React.FC<{ score: number; max?: number }> = ({ score, max = 100 }) => {
  const pct = Math.min(100, Math.round((score / max) * 100));
  const color = pct >= 70 ? '#4caf50' : pct >= 40 ? '#ff9800' : '#f44336';
  return (
    <div className="score-bar-container">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="score-bar-value">{score}/{max}</span>
    </div>
  );
};

// Tooltip component for investment terms
const Tooltip: React.FC<{ label: string; tip: string }> = ({ label, tip }) => (
  <span className="tooltip-trigger">
    {label}
    <span className="tooltip-icon">?</span>
    <span className="tooltip-content">{tip}</span>
  </span>
);

// Format currency
const fmtCurrency = (n: number | null | undefined) => {
  if (n === null || n === undefined) return '—';
  return '$' + Math.round(n).toLocaleString();
};

// Sale Price Prediction display
const SalePricePrediction: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  if (!data) return null;

  const predictedPrice = data.predicted_sale_price;
  const priceRange = data.price_range || {};
  const adjustmentFactors = data.adjustment_factors || [];
  const marketSnapshot = data.market_snapshot || {};
  const vsListPct = data.vs_list_price_pct;
  const vsRedfinPct = data.vs_redfin_estimate_pct;
  const confidence = data.confidence || 'medium';
  const confidenceScore = data.score || 50;

  if (!predictedPrice) return null;

  const formatPriceK = (n: number) => {
    if (n >= 1000000) return `$${(n / 1000000).toFixed(2)}M`;
    return `$${Math.round(n / 1000)}K`;
  };

  const getDirectionIcon = (direction: string) => {
    return direction === 'up' ? '↑' : '↓';
  };

  const getDirectionClass = (direction: string) => {
    return direction === 'up' ? 'factor-up' : 'factor-down';
  };

  const getImpactClass = (impact: string) => {
    if (impact === 'significant') return 'impact-significant';
    if (impact === 'moderate') return 'impact-moderate';
    return 'impact-slight';
  };

  return (
    <div className="sale-price-prediction">
      {/* Main price range display */}
      <div className="price-range-display">
        <div className="price-range-bar">
          <span className="range-low">{formatPriceK(priceRange.low)}</span>
          <div className="range-track">
            <div className="range-marker" style={{ left: '50%' }}>
              <span className="predicted-price">{formatPriceK(predictedPrice)}</span>
              <span className="predicted-label">predicted</span>
            </div>
          </div>
          <span className="range-high">{formatPriceK(priceRange.high)}</span>
        </div>
      </div>

      {/* Comparisons */}
      <div className="price-comparisons">
        {vsListPct !== null && vsListPct !== undefined && (
          <div className={`comparison-chip ${vsListPct > 0 ? 'chip-positive' : vsListPct < 0 ? 'chip-negative' : ''}`}>
            vs List: {vsListPct > 0 ? '+' : ''}{vsListPct.toFixed(1)}%
          </div>
        )}
        {vsRedfinPct !== null && vsRedfinPct !== undefined && (
          <div className={`comparison-chip ${vsRedfinPct > 0 ? 'chip-positive' : vsRedfinPct < 0 ? 'chip-negative' : ''}`}>
            vs Estimate: {vsRedfinPct > 0 ? '+' : ''}{vsRedfinPct.toFixed(1)}%
          </div>
        )}
        <div className={`confidence-chip confidence-${confidence}`}>
          {confidence} confidence ({confidenceScore}/100)
        </div>
      </div>

      {/* Adjustment factors */}
      {adjustmentFactors.length > 0 && (
        <div className="adjustment-factors">
          <strong>Adjustment Factors:</strong>
          <div className="factors-list">
            {adjustmentFactors.map((f: any, i: number) => (
              <div key={i} className={`factor-item ${getDirectionClass(f.direction)} ${getImpactClass(f.impact)}`}>
                <span className="factor-icon">{getDirectionIcon(f.direction)}</span>
                <span className="factor-text">{f.factor}</span>
                <span className="factor-impact">({f.impact})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Market snapshot */}
      {marketSnapshot.mortgage_rate && (
        <div className="market-snapshot-bar">
          <span>{marketSnapshot.market_type || 'Balanced'} market</span>
          <span className="snapshot-divider">•</span>
          <span>Rates {marketSnapshot.mortgage_rate}%</span>
          {marketSnapshot.local_trend && marketSnapshot.local_trend !== 'unknown' && (
            <>
              <span className="snapshot-divider">•</span>
              <span>{marketSnapshot.local_trend}</span>
            </>
          )}
        </div>
      )}
    </div>
  );
};

// Investment metrics display with formulas
const InvestmentMetrics: React.FC<{ metrics: Record<string, any> }> = ({ metrics }) => {
  if (!metrics) return null;

  const price = metrics.purchase_price;
  const rent = metrics.monthly_rent;
  const noi = metrics.noi;
  const downPayment = metrics.down_payment;
  const annualCashFlow = metrics.annual_cash_flow;
  const annualRent = rent ? rent * 12 : null;

  const getValueClass = (value: number | null, good: number, bad: number, higher: boolean) => {
    if (value === null || value === undefined) return '';
    if (higher) {
      return value >= good ? 'positive' : value <= bad ? 'negative' : 'neutral';
    }
    return value <= good ? 'positive' : value >= bad ? 'negative' : 'neutral';
  };

  return (
    <div className="investment-formulas">
      {/* Gross Yield */}
      {metrics.gross_yield_pct != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Gross Rental Yield</span>
            <span className={`formula-result ${getValueClass(metrics.gross_yield_pct, 6, 4, true)}`}>
              {metrics.gross_yield_pct.toFixed(1)}%
            </span>
          </div>
          <div className="formula-steps">
            <div className="formula-line">= Annual Rent / Purchase Price × 100</div>
            <div className="formula-line">= {fmtCurrency(annualRent)} / {fmtCurrency(price)} × 100</div>
          </div>
          <div className="formula-benchmark">Benchmark: &lt;4% poor, 4-6% fair, 6-8% good, &gt;8% excellent</div>
        </div>
      )}

      {/* Cap Rate */}
      {metrics.cap_rate_pct != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Cap Rate</span>
            <span className={`formula-result ${getValueClass(metrics.cap_rate_pct, 6, 3, true)}`}>
              {metrics.cap_rate_pct.toFixed(1)}%
            </span>
          </div>
          <div className="formula-steps">
            <div className="formula-line">= NOI / Purchase Price × 100</div>
            <div className="formula-line">= {fmtCurrency(noi)} / {fmtCurrency(price)} × 100</div>
          </div>
          <div className="formula-detail">
            NOI = Effective Income − Operating Expenses
            <br />
            = {fmtCurrency(metrics.effective_income)} − {fmtCurrency(metrics.operating_expenses)}
          </div>
          <div className="formula-benchmark">Benchmark: &lt;4% appreciation play, 4-6% moderate, 6-10% good</div>
        </div>
      )}

      {/* GRM */}
      {metrics.grm != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Gross Rent Multiplier (GRM)</span>
            <span className={`formula-result ${getValueClass(metrics.grm, 15, 20, false)}`}>
              {metrics.grm.toFixed(1)}
            </span>
          </div>
          <div className="formula-steps">
            <div className="formula-line">= Purchase Price / Annual Rent</div>
            <div className="formula-line">= {fmtCurrency(price)} / {fmtCurrency(annualRent)}</div>
          </div>
          <div className="formula-benchmark">Benchmark: &lt;12 excellent, 12-15 good, 15-20 fair, &gt;20 poor</div>
        </div>
      )}

      {/* Cash-on-Cash */}
      {metrics.cash_on_cash_pct != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Cash-on-Cash Return</span>
            <span className={`formula-result ${getValueClass(metrics.cash_on_cash_pct, 4, 0, true)}`}>
              {metrics.cash_on_cash_pct.toFixed(1)}%
            </span>
          </div>
          <div className="formula-steps">
            <div className="formula-line">= Annual Cash Flow / Down Payment × 100</div>
            <div className="formula-line">= {fmtCurrency(annualCashFlow)} / {fmtCurrency(downPayment)} × 100</div>
          </div>
          <div className="formula-detail">
            Assumes: 20% down ({fmtCurrency(downPayment)}), 7% rate, 30yr
            <br />
            Monthly mortgage: {fmtCurrency(metrics.monthly_mortgage)}
          </div>
          <div className="formula-benchmark">Benchmark: &lt;0% negative, 0-4% break-even, &gt;4% good</div>
        </div>
      )}

      {/* Monthly Cash Flow */}
      {metrics.monthly_cash_flow != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Monthly Cash Flow</span>
            <span className={`formula-result ${getValueClass(metrics.monthly_cash_flow, 200, 0, true)}`}>
              {fmtCurrency(metrics.monthly_cash_flow)}
            </span>
          </div>
          <div className="formula-steps">
            <div className="formula-line">= (NOI − Annual Debt Service) / 12</div>
            <div className="formula-line">= ({fmtCurrency(noi)} − {fmtCurrency(metrics.annual_debt_service)}) / 12</div>
          </div>
          <div className="formula-benchmark">What you pocket (or pay) monthly after all expenses</div>
        </div>
      )}

      {/* Appreciation */}
      {metrics.appreciation_pct != null && (
        <div className="formula-card">
          <div className="formula-header">
            <span className="formula-name">Area Appreciation</span>
            <span className={`formula-result ${getValueClass(metrics.appreciation_pct, 5, 2, true)}`}>
              {metrics.appreciation_pct.toFixed(1)}%/yr
            </span>
          </div>
          <div className="formula-detail">
            Historical annual price growth for this area
            {metrics.appreciation_5yr != null && (
              <><br />5-year projected growth: {metrics.appreciation_5yr.toFixed(1)}%</>
            )}
          </div>
          <div className="formula-benchmark">Source: {metrics.appreciation_source || 'estimate'}</div>
        </div>
      )}
    </div>
  );
};

const ChatPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, updateBalance } = useAuth();
  const address = searchParams.get('address');

  const [messages, setMessages] = useState<Message[]>([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStep, setCurrentStep] = useState<string>('');
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [extractedSteps, setExtractedSteps] = useState<ExtractedStep[]>([]);
  const [finalData, setFinalData] = useState<Record<string, any> | null>(null);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [inputMessage, setInputMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [signupPrompt, setSignupPrompt] = useState(false);
  const [documentAnalyses, setDocumentAnalyses] = useState<DocumentStatusResponse[]>([]);
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState<string | null>(null);
  const [favoriteLoading, setFavoriteLoading] = useState(false);
  const [genericKnowledge, setGenericKnowledge] = useState<GenericKnowledgePoint[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const analysisStarted = useRef(false);
  const analysisCompleted = useRef(false);

  const handleDocumentAnalysisComplete = (result: DocumentStatusResponse) => {
    setDocumentAnalyses(prev => [...prev, result]);
    // Add a message to the chat about the document analysis
    if (result.result) {
      const docType = result.document_type === 'inspection' ? 'Inspection Report' : 'HOA Document';
      addMessage(
        'assistant',
        `**${docType} Analysis Complete**\n\nScore: ${result.result.score}/100\n\n${result.result.reasoning}`,
        'analysis'
      );
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (address && !analysisStarted.current) {
      analysisStarted.current = true;
      startStreamingAnalysis(address);
    }
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [address]);

  // Check if property is favorited when address changes
  useEffect(() => {
    const checkFavorite = async () => {
      if (address && user) {
        try {
          const result = await favoritesApi.check(address);
          setIsFavorite(result.is_favorite);
          setFavoriteId(result.favorite_id || null);
        } catch (err) {
          // Ignore errors - user might not be logged in
        }
      }
    };
    checkFavorite();
  }, [address, user]);

  const toggleFavorite = async () => {
    if (!address || !user || favoriteLoading) return;

    setFavoriteLoading(true);
    try {
      if (isFavorite && favoriteId) {
        await favoritesApi.remove(favoriteId);
        setIsFavorite(false);
        setFavoriteId(null);
      } else {
        const result = await favoritesApi.add({ address });
        setIsFavorite(true);
        setFavoriteId(result.id);
      }
    } catch (err: any) {
      console.error('Failed to toggle favorite:', err);
    } finally {
      setFavoriteLoading(false);
    }
  };

  const startStreamingAnalysis = async (propertyAddress: string) => {
    setAnalyzing(true);
    analysisCompleted.current = false;
    setMessages([{
      role: 'assistant',
      content: `Starting property analysis for **${propertyAddress}**...`,
      type: 'status'
    }]);

    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const encodedAddress = encodeURIComponent(propertyAddress);
    const token = localStorage.getItem('auth_token');
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const url = `${apiUrl}/api/v1/streaming/analyze/stream/${encodedAddress}${tokenParam}`;

    const es = new EventSource(url);

    es.addEventListener('init', (_e) => {
      setCurrentStep('Initializing analysis...');
    });

    // Heartbeat events keep the connection alive when tab is backgrounded
    es.addEventListener('heartbeat', (_e) => {
      // Connection is still alive - no action needed
      console.debug('SSE heartbeat received');
    });

    es.addEventListener('status', (e) => {
      const data = JSON.parse(e.data);
      setCurrentStep(data.message);
    });

    es.addEventListener('data', (e) => {
      const data = JSON.parse(e.data);
      setCurrentStep(`Extracted: ${data.step_name}`);
      setCompletedSteps(prev => new Set(prev).add(data.step));
      setExtractedSteps(prev => [...prev, {
        step: data.step,
        step_name: data.step_name,
        data: data.data || {},
        timestamp: new Date().toISOString()
      }]);
    });

    es.addEventListener('analysis', (e) => {
      const data = JSON.parse(e.data);
      const stepNum = data.step;
      // Store both the markdown text and structured data (score, strengths, concerns)
      const analysisPayload = {
        _analysis: data.analysis,
        ...(data.data || {}),
      };
      setExtractedSteps(prev => {
        const existing = prev.find(s => s.step === stepNum);
        if (existing) {
          return prev.map(s => s.step === stepNum
            ? { ...s, data: { ...s.data, ...analysisPayload } }
            : s
          );
        }
        return [...prev, {
          step: stepNum,
          step_name: data.step_name,
          data: analysisPayload,
          timestamp: new Date().toISOString()
        }];
      });
      setCompletedSteps(prev => new Set(prev).add(stepNum));

      const analysisHeader = `### ${data.step_name} Analysis\n\n`;
      addMessage('assistant', analysisHeader + data.analysis, 'analysis', data.step, data.step_name);
    });

    es.addEventListener('generic_knowledge', (e) => {
      const data = JSON.parse(e.data);
      if (data.data?.knowledge_points) {
        setGenericKnowledge(data.data.knowledge_points);
        setCompletedSteps(prev => new Set(prev).add(11));
      }
    });

    es.addEventListener('summary', (e) => {
      const data = JSON.parse(e.data);
      analysisCompleted.current = true;
      setAnalyzing(false);
      setCurrentStep('');

      // Update credit balance from server
      if (data.credit_balance !== undefined) {
        updateBalance(data.credit_balance);
      }

      if (data.extracted_data) {
        setFinalData(data.extracted_data);
      }

      // Also capture analysis_results from summary (for cached mode or if analysis events were missed)
      if (data.analysis_results) {
        if (data.analysis_results.property) {
          setExtractedSteps(prev => {
            const has7 = prev.find(s => s.step === 7);
            if (has7) return prev;
            return [...prev, { step: 7, step_name: 'Property Condition', data: data.analysis_results.property, timestamp: new Date().toISOString() }];
          });
          setCompletedSteps(prev => new Set(prev).add(7));
        }
        if (data.analysis_results.location) {
          setExtractedSteps(prev => {
            const has8 = prev.find(s => s.step === 8);
            if (has8) return prev;
            return [...prev, { step: 8, step_name: 'Location & Commute', data: data.analysis_results.location, timestamp: new Date().toISOString() }];
          });
          setCompletedSteps(prev => new Set(prev).add(8));
        }
        if (data.analysis_results.schools) {
          setExtractedSteps(prev => {
            const has9 = prev.find(s => s.step === 9);
            if (has9) return prev;
            return [...prev, { step: 9, step_name: 'School Quality', data: data.analysis_results.schools, timestamp: new Date().toISOString() }];
          });
          setCompletedSteps(prev => new Set(prev).add(9));
        }
        if (data.analysis_results.investment) {
          setExtractedSteps(prev => {
            const has10 = prev.find(s => s.step === 10);
            if (has10) return prev;
            return [...prev, { step: 10, step_name: 'Investment Potential', data: data.analysis_results.investment, timestamp: new Date().toISOString() }];
          });
          setCompletedSteps(prev => new Set(prev).add(10));
        }
        if (data.analysis_results.sale_price) {
          setExtractedSteps(prev => {
            const has12 = prev.find(s => s.step === 12);
            if (has12) return prev;
            return [...prev, { step: 12, step_name: 'Sale Price Prediction', data: data.analysis_results.sale_price, timestamp: new Date().toISOString() }];
          });
          setCompletedSteps(prev => new Set(prev).add(12));
        }
      }

      setTimeout(() => {
        const balanceStr = data.credit_balance !== undefined
          ? `- Credits remaining: $${data.credit_balance.toFixed(2)}\n`
          : '';
        addMessage('assistant',
          `\n\n---\n\n**Analysis Complete!**\n\n` +
          balanceStr +
          `- Time: ${data.total_time?.toFixed(1) || '0'} seconds\n\n` +
          `Use the input below to ask follow-up questions about this property.`,
          'status'
        );
      }, 500);

      es.close();
    });

    es.addEventListener('complete', (_e) => {
      setAnalyzing(false);
      setCurrentStep('');
      es.close();
    });

    es.addEventListener('error', async (e: any) => {
      es.close();

      // If analysis already completed successfully, ignore the error event
      // (EventSource fires error when connection closes, even after success)
      if (analysisCompleted.current) {
        return;
      }

      if (e.data) {
        // Server-sent error event with data payload
        const data = JSON.parse(e.data);
        addMessage('assistant', `Error: ${data.error}`, 'error');
      } else {
        // Connection-level error (e.g. HTTP 402) — re-fetch to detect the status
        try {
          const checkResponse = await fetch(url);
          if (checkResponse.status === 402) {
            const errData = await checkResponse.json();
            const detail = errData.detail || {};
            if (detail.action === 'signup') {
              setSignupPrompt(true);
              addMessage('assistant', 'You\'ve used your free analysis. Sign up for an account to analyze more properties.', 'error');
            } else {
              setSignupPrompt(true);
              addMessage('assistant', `Insufficient credits (balance: $${(detail.balance || 0).toFixed(2)}). Purchase more credits to continue analyzing properties.`, 'error');
            }
          } else {
            checkResponse.body?.cancel();
            addMessage('assistant', 'Connection lost. Please refresh and try again.', 'error');
          }
        } catch {
          addMessage('assistant', 'Connection lost. Please refresh and try again.', 'error');
        }
      }

      setAnalyzing(false);
      setCurrentStep('');
    });

    setEventSource(es);
  };

  const addMessage = (
    role: 'user' | 'assistant' | 'system',
    content: string,
    type?: string,
    step?: number,
    step_name?: string
  ) => {
    setMessages(prev => [...prev, { role, content, type, step, step_name } as Message]);
  };

  const startNewAnalysis = () => {
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }
    setExtractedSteps([]);
    setFinalData(null);
    setCompletedSteps(new Set());
    setGenericKnowledge([]);
    analysisStarted.current = false;
    analysisCompleted.current = false;
    navigate('/');
  };

  const handleExportPDF = () => {
    window.print();
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || sendingMessage) return;

    const userMessage = inputMessage.trim();
    setInputMessage('');
    setSendingMessage(true);

    // Add user message to chat
    addMessage('user', userMessage);

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const authToken = localStorage.getItem('auth_token');
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      const response = await fetch(`${apiUrl}/api/v1/chat/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: userMessage,
          address: address,
          conversation_id: conversationId,
        })
      });

      if (response.status === 402) {
        const errData = await response.json();
        const detail = errData.detail || {};
        if (detail.action === 'signup') {
          setSignupPrompt(true);
          addMessage('assistant', 'Sign up for an account to continue chatting and unlock more analyses.');
        } else {
          addMessage('assistant', `Insufficient credits (balance: $${(detail.balance || 0).toFixed(2)}). Purchase more credits to continue.`);
        }
        setSendingMessage(false);
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setConversationId(data.conversation_id);
      addMessage('assistant', data.response);

      // Update credit balance from response
      if (data.credit_balance !== undefined) {
        updateBalance(data.credit_balance);
      }
    } catch (error) {
      console.error('Chat error:', error);
      addMessage('assistant', 'Sorry, there was an error processing your message. Please try again.');
    } finally {
      setSendingMessage(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const report = buildReportData(extractedSteps, finalData);
  const isComplete = !analyzing && (finalData !== null || extractedSteps.length > 0);
  const hasAnyData = extractedSteps.length > 0 || finalData !== null;

  // Get analysis step data (includes structured score/strengths/concerns + markdown)
  const getAnalysisStep = (stepNum: number) => {
    return extractedSteps.find(s => s.step === stepNum)?.data || null;
  };

  // Get score: prefer structured data.score, fallback to regex on markdown
  const getScore = (stepData: any): number | null => {
    if (!stepData) return null;
    if (typeof stepData.score === 'number') return stepData.score;
    if (stepData._analysis) {
      const match = stepData._analysis.match(/(\d+)\s*\/\s*100/);
      return match ? parseInt(match[1]) : null;
    }
    return null;
  };

  // Get list: prefer structured array, fallback to parsing markdown
  const getList = (stepData: any, field: string): string[] => {
    if (!stepData) return [];
    // Structured data from analysis event
    if (Array.isArray(stepData[field])) return stepData[field].slice(0, 5);
    // Fallback: parse from markdown
    if (!stepData._analysis) return [];
    const lines = stepData._analysis.split('\n');
    let capture = false;
    const items: string[] = [];
    for (const line of lines) {
      if (line.toLowerCase().includes(field.toLowerCase())) { capture = true; continue; }
      if (capture) {
        if (line.match(/^#{1,3}\s/) || (line.trim() === '' && items.length > 0)) break;
        const cleaned = line.replace(/^[-*•]\s*/, '').trim();
        if (cleaned) items.push(cleaned);
      }
    }
    return items.slice(0, 5);
  };

  const propStep = getAnalysisStep(7);
  const locStep = getAnalysisStep(8);
  const schoolStep = getAnalysisStep(9);
  const investmentStep = getAnalysisStep(10);
  const salePriceStep = getAnalysisStep(12);
  const propAnalysis = propStep?._analysis || null;
  const locAnalysis = locStep?._analysis || null;
  const schoolAnalysis = schoolStep?._analysis || null;
  const investmentAnalysis = investmentStep?._analysis || null;
  const salePriceAnalysis = salePriceStep?._analysis || null;
  const propScore = getScore(propStep);
  const locScore = getScore(locStep);
  const schoolScore = getScore(schoolStep);
  const investmentScore = getScore(investmentStep);
  const salePriceConfidence = getScore(salePriceStep);
  const scoreParts = [propScore, locScore, schoolScore, investmentScore].filter((s): s is number => s !== null);
  const overallScore = scoreParts.length > 0 ? Math.round(scoreParts.reduce((a, b) => a + b, 0) / scoreParts.length) : null;

  return (
    <div className="chat-container">
      <SEOHead
        title={address ? `${address} Analysis - Perchspot` : "Property Analysis - Perchspot"}
        description={address ? `AI analysis of ${address}. View condition, schools, investment potential, and location quality.` : "Analyze any property with AI-powered insights."}
        path={`/chat${address ? `?address=${encodeURIComponent(address)}` : ''}`}
      />
      <div className="chat-header no-print">
        <div className="header-left">
          <Link to="/" className="logo-link">
            <img src={Logo} alt="Perchspot" className="header-logo" />
          </Link>
          {address && <p className="subtitle">{address}</p>}
        </div>
        <div className="header-actions">
          {user && (
            <>
              <Link to="/account" className="account-link">
                My Account
              </Link>
              <Link to="/credits" className="credits-link">
                ${user.credit_balance.toFixed(2)}
              </Link>
            </>
          )}
          <button onClick={startNewAnalysis} className="reset-btn">
            New Analysis
          </button>
        </div>
      </div>

      <div className="chat-content-wrapper">
        {/* Left panel: Chat */}
        <div className="chat-panel no-print">
          {analyzing && currentStep && (
            <div className="progress-indicator">
              <div className="spinner"></div>
              <span>{currentStep}</span>
            </div>
          )}

          <div className="chat-messages">
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                <div className="message-content">
                  <div className="message-text">
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>
                </div>
              </div>
            ))}

            {(analyzing || sendingMessage) && (
              <div className="message assistant">
                <div className="message-content">
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

          {signupPrompt && (
            <div className="signup-prompt">
              <h3>Want to analyze more properties?</h3>
              {user ? (
                <>
                  <p>Your credit balance is $0.00. Purchase credits to continue analyzing properties.</p>
                  <div className="signup-prompt-actions">
                    <Link to="/credits" className="btn-primary">Buy Credits</Link>
                  </div>
                </>
              ) : (
                <>
                  <p>Create an account and purchase credits to unlock more analyses.</p>
                  <div className="signup-prompt-actions">
                    <Link to="/register" className="btn-primary">Sign Up</Link>
                    <Link to="/login" className="btn-secondary">Sign In</Link>
                  </div>
                </>
              )}
            </div>
          )}

          {!address && (
            <div className="no-address-prompt">
              <h2>No property address provided</h2>
              <p>Please go back to the home page and enter a property address to analyze.</p>
              <button onClick={() => navigate('/')} className="btn-primary">
                Go to Home
              </button>
            </div>
          )}

          {/* Chat input */}
          {address && isComplete && (
            <div className="chat-input-container">
              <input
                type="text"
                className="chat-input"
                placeholder="Ask a follow-up question..."
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={sendingMessage}
              />
              <button
                className="send-btn"
                onClick={handleSendMessage}
                disabled={sendingMessage || !inputMessage.trim()}
              >
                {sendingMessage ? '...' : 'Send'}
              </button>
            </div>
          )}
        </div>

        {/* Right panel: Property Report */}
        <div className="report-panel">
          {/* Print-only header with logo */}
          <div className="print-header">
            <div className="print-header-left">
              <img src={Logo} alt="Perchspot" className="print-logo" />
              <div className="print-brand">
                <p className="print-brand-name">Perchspot</p>
                <p className="print-brand-tagline">AI-Powered Property Analysis</p>
              </div>
            </div>
            <div className="print-header-right">
              {address && <p className="print-address">{address}</p>}
              <p className="print-date">Generated {new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
            </div>
          </div>

          <div className="report-header">
            <div>
              <h3>Property Report</h3>
              {address && <p className="report-address">{address}</p>}
            </div>
            <div className="report-actions">
              {address && isComplete && (
                <ShareButtons
                  address={address}
                  score={overallScore}
                  grade={getGrade(overallScore)}
                  price={get(report.property, 'list_price') || get(report.property, 'price')}
                  beds={get(report.property, 'bedrooms') || get(report.property, 'beds')}
                  baths={get(report.property, 'bathrooms') || get(report.property, 'baths')}
                  sqft={get(report.property, 'living_area_sqft') || get(report.property, 'sqft')}
                />
              )}
              {user && address && (
                <button
                  className={`favorite-btn ${isFavorite ? 'is-favorite' : ''}`}
                  onClick={toggleFavorite}
                  disabled={favoriteLoading}
                  title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                >
                  <svg viewBox="0 0 24 24" fill={isFavorite ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                </button>
              )}
              <button
                className="export-btn"
                onClick={handleExportPDF}
                disabled={!isComplete}
              >
                Export PDF
              </button>
            </div>
          </div>

          <div className="report-content">
            {/* Overall score banner */}
            {overallScore !== null && (
              <div className="report-section report-overall fade-in">
                <div className="overall-score-row">
                  <ScoreCircle value={overallScore} label="Overall" />
                  {propScore !== null && <ScoreCircle value={propScore} label="Property" />}
                  {locScore !== null && <ScoreCircle value={locScore} label="Location" />}
                  {schoolScore !== null && <ScoreCircle value={schoolScore} label="Schools" />}
                  {investmentScore !== null && <ScoreCircle value={investmentScore} label="Investment" />}
                </div>
              </div>
            )}

            {/* Step 1: Screenshots / capturing */}
            {(analyzing && !completedSteps.has(2)) && !report.property && (
              <div className="report-section report-capturing">
                <div className="capturing-indicator">
                  <div className="spinner-small"></div>
                  <span>Gathering property data...</span>
                </div>
              </div>
            )}
            {completedSteps.has(1) && !report.property && (
              <div className="report-section report-capturing fade-in">
                <span className="check">✓</span> Data collected
              </div>
            )}

            {/* Step 2: Property Overview */}
            {report.property ? (
              <div className="report-section property-overview fade-in">
                <h4>Property Overview</h4>
                {/* Property Photo */}
                {report.images?.main_photo_url && (
                  <div className="property-photo-container">
                    <img
                      src={report.images.main_photo_url}
                      alt={address || 'Property photo'}
                      className="property-main-photo"
                      onError={(e) => {
                        // Hide image if it fails to load
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}
                <div className="property-header-row">
                  <span className="property-price">{formatPrice(get(report.property, 'list_price') || get(report.property, 'price'))}</span>
                  {get(report.property, 'status') && (
                    <span className="status-badge">{get(report.property, 'status')}</span>
                  )}
                </div>
                <div className="property-details-row">
                  {(get(report.property, 'bedrooms') || get(report.property, 'beds')) && <span>{get(report.property, 'bedrooms') || get(report.property, 'beds')} beds</span>}
                  {(get(report.property, 'bathrooms') || get(report.property, 'baths')) && <span>{get(report.property, 'bathrooms') || get(report.property, 'baths')} baths</span>}
                  {(get(report.property, 'living_area_sqft') || get(report.property, 'sqft')) && <span>{Number(get(report.property, 'living_area_sqft') || get(report.property, 'sqft')).toLocaleString()} sqft</span>}
                  {(get(report.property, 'lot_size_sqft') || get(report.property, 'lot_size')) && <span>{Number(get(report.property, 'lot_size_sqft') || get(report.property, 'lot_size')).toLocaleString()} sqft lot</span>}
                  {get(report.property, 'year_built') && <span>Built {get(report.property, 'year_built')}</span>}
                </div>
                {get(report.property, 'description') && (
                  <details className="property-description">
                    <summary>Description</summary>
                    <p>{get(report.property, 'description')}</p>
                  </details>
                )}
              </div>
            ) : completedSteps.has(1) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /><div className="skeleton-block short" /></div>
            ) : null}

            {/* Step 3: Pricing */}
            {report.pricing ? (
              <div className="report-section pricing fade-in">
                <h4>Pricing</h4>
                <table className="report-table">
                  <tbody>
                    {get(report.pricing, 'list_price') && (
                      <tr><td>List Price</td><td>{formatPrice(get(report.pricing, 'list_price'))}</td></tr>
                    )}
                    {(get(report.pricing, 'redfin_estimate') || get(report.pricing, 'estimate')) && (
                      <tr><td>Estimated Value</td><td>{formatPrice(get(report.pricing, 'redfin_estimate') || get(report.pricing, 'estimate'))}</td></tr>
                    )}
                    {get(report.pricing, 'rental_estimate') && (
                      <tr><td>Rental Estimate</td><td>{formatPrice(get(report.pricing, 'rental_estimate'))}/mo</td></tr>
                    )}
                    {get(report.pricing, 'price_per_sqft') && (
                      <tr><td>Price/sqft</td><td>{formatPrice(get(report.pricing, 'price_per_sqft'))}</td></tr>
                    )}
                    {get(report.pricing, 'hoa') && (
                      <tr><td>HOA</td><td>{get(report.pricing, 'hoa')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : hasAnyData && !completedSteps.has(3) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block short" /></div>
            ) : null}

            {/* Step 4: Schools */}
            {report.schools ? (
              <div className="report-section schools fade-in">
                <h4>Schools</h4>
                {Array.isArray(report.schools) ? (
                  <table className="report-table schools-table">
                    <thead>
                      <tr><th>School</th><th>Type</th><th>Rating</th><th>Dist.</th></tr>
                    </thead>
                    <tbody>
                      {report.schools.map((s: any, i: number) => (
                        <tr key={i}>
                          <td>{s.name || s.school_name || '—'}</td>
                          <td>{s.type || s.school_type || '—'}</td>
                          <td>
                            <div className="rating-bar">
                              <div className="rating-fill" style={{ width: `${((s.rating || s.score || 0) / 10) * 100}%` }} />
                            </div>
                            <span className="rating-num">{s.rating || s.score || '—'}/10</span>
                          </td>
                          <td>{s.distance || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="section-data-fallback">
                    {Object.entries(report.schools).map(([k, v]) => (
                      <div key={k} className="data-row"><span>{k}</span><span>{String(v)}</span></div>
                    ))}
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(4) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 5: Location */}
            {report.location ? (
              <div className="report-section location fade-in">
                <h4>Location Scores</h4>
                <div className="scores-row">
                  {(get(report.location, 'walkability_score') ?? get(report.location, 'walk_score')) != null && (
                    <ScoreCircle value={get(report.location, 'walkability_score') ?? get(report.location, 'walk_score')} label="Walk" />
                  )}
                  {get(report.location, 'transit_score') != null && (
                    <ScoreCircle value={get(report.location, 'transit_score')} label="Transit" />
                  )}
                  {get(report.location, 'bike_score') != null && (
                    <ScoreCircle value={get(report.location, 'bike_score')} label="Bike" />
                  )}
                </div>
                {(get(report.location, 'market_type') || get(report.location, 'market')) && (
                  <p className="location-market">Market: {get(report.location, 'market_type') || get(report.location, 'market')}</p>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(5) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block short" /></div>
            ) : null}

            {/* Step 6: Climate */}
            {report.climate ? (
              <div className="report-section climate fade-in">
                <h4>Climate Risks</h4>
                <div className="risk-chips">
                  {(Array.isArray(report.climate) ? report.climate : Object.entries(report.climate)
                    .filter(([k]) => k !== 'air_quality')
                    .map(([k, v]) => ({
                    factor: k,
                    level: typeof v === 'string' ? v : (v as any)?.level || (v as any)?.risk || String(v)
                  }))).map((risk: any, i: number) => (
                    <span
                      key={i}
                      className="risk-chip"
                      style={{ background: getRiskColor(risk.level || risk.risk || '') + '22', color: getRiskColor(risk.level || risk.risk || ''), borderColor: getRiskColor(risk.level || risk.risk || '') }}
                    >
                      {risk.factor || risk.type || risk.name}: {risk.level || risk.risk || '—'}
                    </span>
                  ))}
                </div>
              </div>
            ) : hasAnyData && !completedSteps.has(6) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block short" /></div>
            ) : null}

            {/* Step 7: Property Analysis */}
            {propAnalysis ? (
              <div className="report-section analysis-property fade-in">
                <h4>Property Condition</h4>
                {propScore !== null && <ScoreBar score={propScore} />}
                {getList(propStep, 'strengths').length > 0 && (
                  <div className="analysis-list">
                    <strong>Strengths</strong>
                    <ul>{getList(propStep, 'strengths').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
                {getList(propStep, 'concerns').length > 0 && (
                  <div className="analysis-list">
                    <strong>Concerns</strong>
                    <ul>{getList(propStep, 'concerns').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(7) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 8: Location Analysis */}
            {locAnalysis ? (
              <div className="report-section analysis-location fade-in">
                <h4>Location Quality</h4>
                {locScore !== null && <ScoreBar score={locScore} />}
                {getList(locStep, 'strengths').length > 0 && (
                  <div className="analysis-list">
                    <strong>Strengths</strong>
                    <ul>{getList(locStep, 'strengths').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
                {getList(locStep, 'concerns').length > 0 && (
                  <div className="analysis-list">
                    <strong>Concerns</strong>
                    <ul>{getList(locStep, 'concerns').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(8) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 9: School Analysis */}
            {schoolAnalysis ? (
              <div className="report-section analysis-schools fade-in">
                <h4>School Quality</h4>
                {schoolScore !== null && <ScoreBar score={schoolScore} />}
                {getList(schoolStep, 'strengths').length > 0 && (
                  <div className="analysis-list">
                    <strong>Strengths</strong>
                    <ul>{getList(schoolStep, 'strengths').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
                {getList(schoolStep, 'concerns').length > 0 && (
                  <div className="analysis-list">
                    <strong>Concerns</strong>
                    <ul>{getList(schoolStep, 'concerns').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(9) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 10: Investment Analysis */}
            {investmentAnalysis ? (
              <div className="report-section analysis-investment fade-in">
                <h4>Investment Potential</h4>
                {investmentScore !== null && <ScoreBar score={investmentScore} />}
                {investmentStep?.details?.computed_metrics && (
                  <InvestmentMetrics metrics={investmentStep.details.computed_metrics} />
                )}
                {getList(investmentStep, 'strengths').length > 0 && (
                  <div className="analysis-list">
                    <strong>Strengths</strong>
                    <ul>{getList(investmentStep, 'strengths').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
                {getList(investmentStep, 'concerns').length > 0 && (
                  <div className="analysis-list">
                    <strong>Concerns</strong>
                    <ul>{getList(investmentStep, 'concerns').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(10) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 12: Sale Price Prediction */}
            {salePriceAnalysis ? (
              <div className="report-section analysis-saleprice fade-in">
                <h4>Predicted Sale Price</h4>
                <SalePricePrediction data={salePriceStep} />
                {salePriceStep?.reasoning && (
                  <p className="prediction-reasoning">{salePriceStep.reasoning}</p>
                )}
                {getList(salePriceStep, 'strengths').length > 0 && (
                  <div className="analysis-list">
                    <strong>Price Strengths</strong>
                    <ul>{getList(salePriceStep, 'strengths').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
                {getList(salePriceStep, 'concerns').length > 0 && (
                  <div className="analysis-list">
                    <strong>Price Concerns</strong>
                    <ul>{getList(salePriceStep, 'concerns').map((s, i) => <li key={i}>{s}</li>)}</ul>
                  </div>
                )}
              </div>
            ) : hasAnyData && !completedSteps.has(12) && analyzing ? (
              <div className="report-section skeleton"><div className="skeleton-block" /></div>
            ) : null}

            {/* Step 11: Property Insights (Generic Knowledge) */}
            {genericKnowledge.length > 0 && (
              <div className="report-section property-insights fade-in">
                <h4>Property Insights</h4>
                <p className="insights-intro">Based on this property's characteristics:</p>
                <div className="insights-list">
                  {genericKnowledge.filter(k => k.priority === 'high').map((k, i) => (
                    <div key={`high-${i}`} className="insight-item high-priority">
                      <span className="priority-badge high">Important</span>
                      <p className="insight-text">{k.text}</p>
                      <span className="insight-category">{k.category}</span>
                    </div>
                  ))}
                  {genericKnowledge.filter(k => k.priority !== 'high').map((k, i) => (
                    <div key={`other-${i}`} className="insight-item">
                      <p className="insight-text">{k.text}</p>
                      <span className="insight-category">{k.category}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Document Upload - shown after analysis is complete */}
            {address && isComplete && (
              <DocumentUpload
                address={address}
                onAnalysisComplete={handleDocumentAnalysisComplete}
                onBalanceUpdate={updateBalance}
              />
            )}

            {/* Referral prompt - shown after analysis for logged in users */}
            {address && isComplete && user && (
              <ReferralPrompt />
            )}

            {/* Empty state */}
            {!hasAnyData && !analyzing && (
              <div className="report-empty">
                <p>Property report will appear here as data is analyzed.</p>
              </div>
            )}
          </div>

          {/* Powered by Perchspot badge - visible after analysis */}
          {isComplete && (
            <div className="powered-by-badge">
              <img src={Logo} alt="Perchspot" className="badge-logo" />
              <span>Powered by <a href="https://perchspot.com" target="_blank" rel="noopener noreferrer">Perchspot</a></span>
            </div>
          )}

          {/* Print-only footer */}
          <div className="print-footer">
            <p>This report was generated by <a href="https://perchspot.com">Perchspot</a> - AI-Powered Property Analysis</p>
            <p>For the most up-to-date analysis, visit perchspot.com</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
