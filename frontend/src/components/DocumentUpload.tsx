import React, { useState, useRef } from 'react';
import { documentsApi } from '../services/api';
import type { DocumentType, DocumentStatusResponse } from '../types';
import './DocumentUpload.css';

interface DocumentUploadProps {
  address: string;
  onAnalysisComplete?: (result: DocumentStatusResponse) => void;
  onBalanceUpdate?: (balance: number) => void;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({
  address,
  onAnalysisComplete,
  onBalanceUpdate,
}) => {
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DocumentStatusResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedType, setSelectedType] = useState<DocumentType | 'auto'>('auto');

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a PDF file');
      return;
    }

    // Validate file size (max 20MB)
    if (file.size > 20 * 1024 * 1024) {
      setError('File is too large. Maximum size is 20MB');
      return;
    }

    setError(null);
    setResult(null);
    setUploading(true);
    setProgress('Uploading document...');

    try {
      // Upload document
      const uploadResponse = await documentsApi.uploadDocument(
        address,
        file,
        selectedType
      );

      if (uploadResponse.status === 'error') {
        throw new Error(uploadResponse.message || 'Upload failed');
      }

      // Update balance from upload response (credits deducted upfront)
      if (uploadResponse.credit_balance !== undefined) {
        onBalanceUpdate?.(uploadResponse.credit_balance);
      }

      setUploading(false);
      setAnalyzing(true);
      setProgress(`Analyzing ${uploadResponse.document_type} document...`);

      // Poll for completion
      const statusResponse = await documentsApi.waitForCompletion(
        uploadResponse.job_id,
        1000,
        120
      );

      setAnalyzing(false);

      if (statusResponse.status === 'failed') {
        throw new Error(statusResponse.error || 'Analysis failed');
      }

      // Update balance from final status (in case it changed)
      if (statusResponse.credit_balance !== undefined) {
        onBalanceUpdate?.(statusResponse.credit_balance);
      }

      setResult(statusResponse);
      setProgress('');
      onAnalysisComplete?.(statusResponse);
    } catch (err: any) {
      setUploading(false);
      setAnalyzing(false);
      setProgress('');

      if (err.response?.status === 402) {
        const detail = err.response.data?.detail;
        if (typeof detail === 'object') {
          setError(
            `Insufficient credits. Balance: $${(detail.balance || 0).toFixed(2)}, Cost: $${(detail.cost || 0).toFixed(2)}`
          );
        } else {
          setError('Insufficient credits for document analysis');
        }
      } else {
        setError(err.message || 'Failed to upload document');
      }
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const triggerFileSelect = (type: DocumentType | 'auto') => {
    setSelectedType(type);
    fileInputRef.current?.click();
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'safety':
        return '#dc3545';
      case 'major':
        return '#fd7e14';
      case 'moderate':
        return '#ffc107';
      case 'minor':
        return '#20c997';
      case 'cosmetic':
        return '#6c757d';
      default:
        return '#6c757d';
    }
  };

  const renderResult = () => {
    if (!result?.result) return null;

    const { result: analysis, document_type } = result;

    return (
      <div className="document-result fade-in">
        <div className="result-header">
          <h4>
            {document_type === 'inspection'
              ? 'Inspection Report Analysis'
              : 'HOA Document Analysis'}
          </h4>
          <div className="result-score">
            <span className="score-value">{analysis.score}</span>
            <span className="score-max">/100</span>
          </div>
        </div>

        <p className="result-reasoning">{analysis.reasoning}</p>

        {analysis.strengths.length > 0 && (
          <div className="result-list strengths">
            <h5>Strengths</h5>
            <ul>
              {analysis.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}

        {analysis.concerns.length > 0 && (
          <div className="result-list concerns">
            <h5>Concerns</h5>
            <ul>
              {analysis.concerns.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Inspection-specific: Issues list */}
        {document_type === 'inspection' && analysis.details?.issues && (
          <div className="issues-list">
            <h5>Issues Found</h5>
            {analysis.details.issues.map((issue: any, i: number) => (
              <div key={i} className="issue-item">
                <div className="issue-header">
                  <span
                    className="severity-badge"
                    style={{ backgroundColor: getSeverityColor(issue.severity) }}
                  >
                    {issue.severity.toUpperCase()}
                  </span>
                  <span className="issue-system">{issue.system}</span>
                </div>
                <p className="issue-description">{issue.description}</p>
                <div className="issue-meta">
                  <span>Est. Cost: {issue.estimated_cost}</span>
                  <span>Urgency: {issue.urgency}</span>
                </div>
              </div>
            ))}
            {analysis.details.total_estimated_repairs && (
              <div className="total-repairs">
                <strong>Total Estimated Repairs:</strong>{' '}
                {analysis.details.total_estimated_repairs}
              </div>
            )}
          </div>
        )}

        {/* HOA-specific: Key details */}
        {document_type === 'hoa' && analysis.details && (
          <div className="hoa-details">
            {analysis.details.monthly_fee != null && (
              <div className="hoa-fee">
                <h5>Monthly Fee</h5>
                <span className="fee-amount">${analysis.details.monthly_fee}</span>
                {analysis.details.fee_includes && (
                  <p className="fee-includes">
                    Includes: {analysis.details.fee_includes.join(', ')}
                  </p>
                )}
              </div>
            )}

            {analysis.details.reserve_fund && (
              <div className="reserve-fund">
                <h5>Reserve Fund</h5>
                <div className="reserve-bar">
                  <div
                    className="reserve-fill"
                    style={{
                      width: `${analysis.details.reserve_fund.funded_percentage || 0}%`,
                      backgroundColor:
                        (analysis.details.reserve_fund.funded_percentage || 0) >= 60
                          ? '#4caf50'
                          : (analysis.details.reserve_fund.funded_percentage || 0) >= 40
                          ? '#ff9800'
                          : '#f44336',
                    }}
                  />
                </div>
                <span className="reserve-pct">
                  {analysis.details.reserve_fund.funded_percentage}% funded
                </span>
              </div>
            )}

            {analysis.details.rental_restrictions && (
              <div className="rental-restrictions">
                <h5>Rental Restrictions</h5>
                <p>
                  {analysis.details.rental_restrictions.allowed
                    ? `Rentals allowed${
                        analysis.details.rental_restrictions.minimum_lease
                          ? ` (min: ${analysis.details.rental_restrictions.minimum_lease})`
                          : ''
                      }`
                    : 'Rentals not allowed'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="document-upload">
      <div className="upload-header">
        <h4>Upload Documents</h4>
        <p>Add inspection reports or HOA documents for detailed analysis</p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />

      <div className="upload-buttons">
        <button
          className="upload-btn inspection"
          onClick={() => triggerFileSelect('inspection')}
          disabled={uploading || analyzing}
        >
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path
              fill="currentColor"
              d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z"
            />
          </svg>
          Upload Inspection Report
        </button>

        <button
          className="upload-btn hoa"
          onClick={() => triggerFileSelect('hoa')}
          disabled={uploading || analyzing}
        >
          <svg viewBox="0 0 24 24" width="20" height="20">
            <path
              fill="currentColor"
              d="M9 16h6v-6h4l-7-7-7 7h4v6zm-4 2h14v2H5v-2z"
            />
          </svg>
          Upload HOA Document
        </button>
      </div>

      {(uploading || analyzing) && (
        <div className="upload-progress">
          <div className="spinner-small" />
          <span>{progress}</span>
        </div>
      )}

      {error && <div className="upload-error">{error}</div>}

      {renderResult()}
    </div>
  );
};

export default DocumentUpload;
