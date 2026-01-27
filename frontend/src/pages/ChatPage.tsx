import React, { useState, useRef, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
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

const ChatPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const address = searchParams.get('address');

  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStep, setCurrentStep] = useState<string>('');
  const [totalCost, setTotalCost] = useState<number>(0);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [extractedSteps, setExtractedSteps] = useState<ExtractedStep[]>([]);
  const [finalData, setFinalData] = useState<Record<string, any> | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Start streaming analysis when address is provided
    if (address && !eventSource) {
      startStreamingAnalysis(address);
    }

    // Cleanup on unmount
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [address]);

  const startStreamingAnalysis = (propertyAddress: string) => {
    setAnalyzing(true);
    setMessages([{
      role: 'assistant',
      content: `Starting property analysis for **${propertyAddress}**...`,
      type: 'status'
    }]);

    // Establish SSE connection
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const encodedAddress = encodeURIComponent(propertyAddress);
    const url = `${apiUrl}/api/v1/streaming/analyze/stream/${encodedAddress}`;

    const es = new EventSource(url);

    // Handle 'init' event (progress indicator only, no chat message)
    es.addEventListener('init', (_e) => {
      setCurrentStep('Initializing analysis...');
    });

    // Handle 'status' event (progress indicator only, no chat message)
    es.addEventListener('status', (e) => {
      const data = JSON.parse(e.data);
      setCurrentStep(data.message);
    });

    // Handle 'data' event (right panel only, no chat message)
    es.addEventListener('data', (e) => {
      const data = JSON.parse(e.data);
      setCurrentStep(`Extracted: ${data.step_name}`);

      // Capture extracted data for right panel
      setExtractedSteps(prev => [...prev, {
        step: data.step,
        step_name: data.step_name,
        data: data.data || {},
        timestamp: new Date().toISOString()
      }]);
    });

    // Handle 'analysis' event (LLM analysis)
    es.addEventListener('analysis', (e) => {
      const data = JSON.parse(e.data);
      const analysisHeader = `### ${data.step_name} Analysis\n\n`;
      addMessage('assistant', analysisHeader + data.analysis, 'analysis', data.step, data.step_name);
    });

    // Handle 'summary' event (final summary)
    es.addEventListener('summary', (e) => {
      const data = JSON.parse(e.data);
      addMessage('assistant', '## Extraction Complete\n\n' + data.content, 'summary');

      setTotalCost(data.total_cost || 0);
      setAnalyzing(false);
      setCurrentStep('');

      // Capture final extracted data for right panel
      if (data.extracted_data) {
        setFinalData(data.extracted_data);
      }

      // Add completion message
      setTimeout(() => {
        addMessage('assistant',
          `\n\n---\n\n✅ **Analysis Complete!**\n\n` +
          `- Total Cost: $${data.total_cost?.toFixed(4) || '0.0000'}\n` +
          `- Time: ${data.total_time?.toFixed(1) || '0'} seconds\n\n` +
          `You can now ask follow-up questions about this property.`,
          'status'
        );
      }, 500);

      es.close();
    });

    // Handle 'complete' event
    es.addEventListener('complete', (e) => {
      const data = JSON.parse(e.data);
      setAnalyzing(false);
      setCurrentStep('');
      es.close();
    });

    // Handle 'error' event
    es.addEventListener('error', (e: any) => {
      if (e.data) {
        const data = JSON.parse(e.data);
        addMessage('assistant', `❌ Error: ${data.error}`, 'error');
      } else {
        addMessage('assistant', '❌ Connection lost. Please refresh and try again.', 'error');
      }
      setAnalyzing(false);
      setCurrentStep('');
      es.close();
    });

    // Handle connection errors
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        console.log('SSE connection closed');
      } else {
        addMessage('assistant', '❌ Connection error. Please check your network and try again.', 'error');
        setAnalyzing(false);
        setCurrentStep('');
        es.close();
      }
    };

    setEventSource(es);
  };

  const addMessage = (
    role: 'user' | 'assistant' | 'system',
    content: string,
    type?: string,
    step?: number,
    step_name?: string
  ) => {
    setMessages(prev => [...prev, {
      role,
      content,
      type,
      step,
      step_name
    } as Message]);
  };

  const startNewAnalysis = () => {
    // Close existing connection
    if (eventSource) {
      eventSource.close();
      setEventSource(null);
    }

    // Reset state
    setExtractedSteps([]);
    setFinalData(null);

    // Navigate back to home
    navigate('/');
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div>
          <h1>🏠 Property Analysis</h1>
          {address && <p className="subtitle">Analyzing: {address}</p>}
        </div>
        <div className="header-actions">
          {totalCost > 0 && (
            <div className="stats">
              <span className="stat">Cost: ${totalCost.toFixed(4)}</span>
            </div>
          )}
          <button onClick={startNewAnalysis} className="reset-btn">
            New Analysis
          </button>
        </div>
      </div>

      <div className="chat-content-wrapper">
        {/* Left panel: Chat */}
        <div className="chat-panel">
          {analyzing && currentStep && (
            <div className="progress-indicator">
              <div className="spinner"></div>
              <span>{currentStep}</span>
            </div>
          )}

          <div className="chat-messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role} ${message.type || ''}`}>
            <div className="message-content">
              <div className="message-header">
                <span className="role-badge">
                  {message.role === 'user' ? '👤 You' :
                   message.role === 'system' ? '🔧 System' :
                   '🤖 Assistant'}
                </span>
                {message.step && message.step_name && (
                  <span className="step-badge">
                    Step {message.step}: {message.step_name}
                  </span>
                )}
              </div>
              <div className="message-text">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {analyzing && (
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

          {!address && (
            <div className="no-address-prompt">
              <h2>No property address provided</h2>
              <p>Please go back to the home page and enter a property address to analyze.</p>
              <button onClick={() => navigate('/')} className="btn-primary">
                Go to Home
              </button>
            </div>
          )}
        </div>

        {/* Right panel: Extracted Data View */}
        <div className="data-panel">
          <div className="data-panel-header">
            <h3>Extracted Data</h3>
            <div className="data-panel-status">
              {analyzing && <><span className="dot"></span> Extracting...</>}
              {!analyzing && finalData && 'Complete'}
              {!analyzing && !finalData && extractedSteps.length === 0 && 'Waiting'}
            </div>
          </div>
          <div className="data-panel-content">
            {/* Show final merged data if available */}
            {finalData && (
              <div className="data-section final-data">
                <h4>Property Data</h4>
                <pre className="data-json">{JSON.stringify(finalData, null, 2)}</pre>
              </div>
            )}

            {/* Show per-step data while extracting (before final data is ready) */}
            {!finalData && extractedSteps.length > 0 && (
              <>
                {extractedSteps.map((step, idx) => (
                  <div key={idx} className="data-section">
                    <h4>Step {step.step}: {step.step_name}</h4>
                    <pre className="data-json">
                      {JSON.stringify(step.data, null, 2)}
                    </pre>
                  </div>
                ))}
              </>
            )}

            {/* Empty state */}
            {!finalData && extractedSteps.length === 0 && (
              <div className="data-empty">
                <p>Property data will appear here as it is extracted.</p>
                {!analyzing && !address && (
                  <p>Enter a property address to begin.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
