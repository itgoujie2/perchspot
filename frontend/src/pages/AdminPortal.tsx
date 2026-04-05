import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  Alert,
  Tabs,
  Tab,
  Chip,
  LinearProgress,
  Card,
  CardContent,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemButton,
  Drawer,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import {
  Lock,
  Upload,
  Search,
  Storage,
  ContentPaste,
  CheckCircle,
  Delete,
  MenuBook,
  Assessment,
  Refresh,
  Visibility,
  Close,
  Home,
  List as ListIcon,
  FilterList,
  People,
  AttachMoney,
  Feedback,
  Star,
  Analytics,
  CheckCircleOutline,
  Error as ErrorIcon,
  Cached,
  Timer,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import './AdminPortal.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SIDEBAR_WIDTH = 240;

interface SearchResult {
  text: string;
  category: string;
  score: number;
  source_file: string;
}

interface CollectionStatus {
  collection: string;
  point_count: number;
  status: string;
}

interface CachedReport {
  filename: string;
  address: string;
  size_bytes: number;
  modified: string;
}

interface CachedReportDetail {
  filename: string;
  address: string;
  content: string;
  parsed: {
    overall_score: number | null;
    overall_grade: string | null;
    scores: {
      property: number | null;
      location: number | null;
      schools: number | null;
      investment: number | null;
    };
    recommendation: string | null;
    tool_results: any[];
  };
}

interface KnowledgePoint {
  id: string;
  text: string;
  category: string;
  source_file: string;
}

interface FilterOptions {
  sources: string[];
  categories: string[];
}

export default function AdminPortal() {
  const navigate = useNavigate();
  const [password, setPassword] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [authError, setAuthError] = useState('');

  // Navigation state
  const [activeSection, setActiveSection] = useState<'knowledge' | 'reports' | 'promos' | 'users' | 'surveys' | 'analytics'>('reports');

  // Knowledge base state
  const [tab, setTab] = useState(0);
  const [status, setStatus] = useState<CollectionStatus | null>(null);
  const [markdownText, setMarkdownText] = useState('');
  const [fileName, setFileName] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [ingestError, setIngestError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(10);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState('');

  // Cached reports state
  const [reports, setReports] = useState<CachedReport[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [reportsError, setReportsError] = useState('');
  const [reportFilter, setReportFilter] = useState('');
  const [selectedReport, setSelectedReport] = useState<CachedReportDetail | null>(null);
  const [reportDetailLoading, setReportDetailLoading] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [reportToDelete, setReportToDelete] = useState<string | null>(null);

  // Browse knowledge points state
  const [browsePoints, setBrowsePoints] = useState<KnowledgePoint[]>([]);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseError, setBrowseError] = useState('');
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ sources: [], categories: [] });
  const [selectedSource, setSelectedSource] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [browseOffset, setBrowseOffset] = useState(0);
  const [hasMorePoints, setHasMorePoints] = useState(true);
  const [pointToDelete, setPointToDelete] = useState<KnowledgePoint | null>(null);
  const [deletePointConfirmOpen, setDeletePointConfirmOpen] = useState(false);
  const [selectedPointIds, setSelectedPointIds] = useState<Set<string>>(new Set());
  const [bulkDeleteConfirmOpen, setBulkDeleteConfirmOpen] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Promo codes state
  const [promoCodes, setPromoCodes] = useState<any[]>([]);
  const [promosLoading, setPromosLoading] = useState(false);
  const [promosError, setPromosError] = useState('');
  const [newPromoAmount, setNewPromoAmount] = useState('5.00');
  const [newPromoMaxUses, setNewPromoMaxUses] = useState('');
  const [newPromoExpiresDate, setNewPromoExpiresDate] = useState('');
  const [newPromoNote, setNewPromoNote] = useState('');
  const [newPromoCustomCode, setNewPromoCustomCode] = useState('');
  const [creatingPromo, setCreatingPromo] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // Users state
  const [users, setUsers] = useState<any[]>([]);
  const [usersSummary, setUsersSummary] = useState<any>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState('');
  const [userFilter, setUserFilter] = useState('');
  const [addCreditsUser, setAddCreditsUser] = useState<any>(null);
  const [addCreditsAmount, setAddCreditsAmount] = useState('');
  const [addCreditsReason, setAddCreditsReason] = useState('');
  const [addCreditsLoading, setAddCreditsLoading] = useState(false);

  // Surveys state
  const [surveys, setSurveys] = useState<any[]>([]);
  const [surveysSummary, setSurveysSummary] = useState<any>(null);
  const [surveysLoading, setSurveysLoading] = useState(false);
  const [surveysError, setSurveysError] = useState('');
  const [selectedSurvey, setSelectedSurvey] = useState<any>(null);

  // Analytics state
  const [analyses, setAnalyses] = useState<any[]>([]);
  const [analysisStats, setAnalysisStats] = useState<any>(null);
  const [analysesLoading, setAnalysesLoading] = useState(false);
  const [analysesError, setAnalysesError] = useState('');
  const [analysisDays, setAnalysisDays] = useState(7);
  const [selectedAnalysis, setSelectedAnalysis] = useState<any>(null);
  const [analysisDetailLoading, setAnalysisDetailLoading] = useState(false);

  const headers = useCallback(() => ({
    'X-Admin-Password': password,
  }), [password]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/status`, {
        headers: headers(),
      });
      if (res.ok) {
        setStatus(await res.json());
      }
    } catch {
      // silently fail
    }
  }, [headers]);

  const fetchReports = useCallback(async () => {
    setReportsLoading(true);
    setReportsError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/cached-reports`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setReports(data.reports);
      } else {
        const err = await res.json();
        setReportsError(err.detail || 'Failed to load reports');
      }
    } catch (e: any) {
      setReportsError('Cannot connect to backend');
    } finally {
      setReportsLoading(false);
    }
  }, [headers]);

  const fetchFilterOptions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/filters`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setFilterOptions(data);
      }
    } catch {
      // silently fail
    }
  }, [headers]);

  const fetchPromoCodes = useCallback(async () => {
    setPromosLoading(true);
    setPromosError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/promo-codes?include_inactive=true`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setPromoCodes(data.promo_codes);
      } else {
        const err = await res.json();
        setPromosError(err.detail || 'Failed to load promo codes');
      }
    } catch {
      setPromosError('Cannot connect to backend');
    } finally {
      setPromosLoading(false);
    }
  }, [headers]);

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/users`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users);
        setUsersSummary(data.summary);
      } else {
        const err = await res.json();
        setUsersError(err.detail || 'Failed to load users');
      }
    } catch {
      setUsersError('Cannot connect to backend');
    } finally {
      setUsersLoading(false);
    }
  }, [headers]);

  const handleAddCredits = async () => {
    if (!addCreditsUser || !addCreditsAmount) return;

    setAddCreditsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/users/${addCreditsUser.id}/add-credits`, {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          amount: parseFloat(addCreditsAmount),
          reason: addCreditsReason || undefined,
        }),
      });

      if (res.ok) {
        // Refresh users list
        fetchUsers();
        // Close dialog
        setAddCreditsUser(null);
        setAddCreditsAmount('');
        setAddCreditsReason('');
      } else {
        const err = await res.json();
        alert(err.detail || 'Failed to add credits');
      }
    } catch {
      alert('Cannot connect to backend');
    } finally {
      setAddCreditsLoading(false);
    }
  };

  const fetchSurveys = useCallback(async () => {
    setSurveysLoading(true);
    setSurveysError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/surveys`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setSurveys(data.surveys);
        setSurveysSummary(data.summary);
      } else {
        const err = await res.json();
        setSurveysError(err.detail || 'Failed to load surveys');
      }
    } catch {
      setSurveysError('Cannot connect to backend');
    } finally {
      setSurveysLoading(false);
    }
  }, [headers]);

  const fetchAnalyses = useCallback(async () => {
    setAnalysesLoading(true);
    setAnalysesError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/analyses?days=${analysisDays}&limit=100`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setAnalyses(data.analyses);
      } else {
        const err = await res.json();
        setAnalysesError(err.detail || 'Failed to load analyses');
      }
    } catch {
      setAnalysesError('Cannot connect to backend');
    } finally {
      setAnalysesLoading(false);
    }
  }, [headers, analysisDays]);

  const fetchAnalysisStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/analyses/stats?days=${analysisDays}`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setAnalysisStats(data);
      }
    } catch {
      // silently fail
    }
  }, [headers, analysisDays]);

  const fetchAnalysisDetail = async (analysisId: string) => {
    setAnalysisDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/analyses/${analysisId}`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedAnalysis(data);
      } else {
        const err = await res.json();
        setAnalysesError(err.detail || 'Failed to load analysis detail');
      }
    } catch {
      setAnalysesError('Cannot load analysis detail');
    } finally {
      setAnalysisDetailLoading(false);
    }
  };

  const createPromoCode = async () => {
    setCreatingPromo(true);
    setPromosError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/promo-codes`, {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          credit_amount: parseFloat(newPromoAmount),
          max_uses: newPromoMaxUses ? parseInt(newPromoMaxUses) : null,
          expires_date: newPromoExpiresDate || null,
          note: newPromoNote || null,
          custom_code: newPromoCustomCode.trim() || null,
        }),
      });
      if (res.ok) {
        setNewPromoNote('');
        setNewPromoCustomCode('');
        setNewPromoExpiresDate('');
        fetchPromoCodes();
      } else {
        const err = await res.json();
        setPromosError(err.detail || 'Failed to create promo code');
      }
    } catch {
      setPromosError('Cannot connect to backend');
    } finally {
      setCreatingPromo(false);
    }
  };

  const deactivatePromoCode = async (code: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/promo-codes/${code}`, {
        method: 'DELETE',
        headers: headers(),
      });
      if (res.ok) {
        fetchPromoCodes();
      }
    } catch {
      // silently fail
    }
  };

  const copyToClipboard = (text: string, code: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const fetchBrowsePoints = useCallback(async (reset: boolean = false) => {
    setBrowseLoading(true);
    setBrowseError('');
    const offset = reset ? 0 : browseOffset;

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/list`, {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          limit: 50,
          offset,
          source_filter: selectedSource || null,
          category_filter: selectedCategory || null,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (reset) {
          setBrowsePoints(data.points);
          setBrowseOffset(data.points.length);
        } else {
          setBrowsePoints(prev => [...prev, ...data.points]);
          setBrowseOffset(prev => prev + data.points.length);
        }
        setHasMorePoints(data.has_more);
      } else {
        const err = await res.json();
        setBrowseError(err.detail || 'Failed to load knowledge points');
      }
    } catch {
      setBrowseError('Cannot connect to backend');
    } finally {
      setBrowseLoading(false);
    }
  }, [headers, browseOffset, selectedSource, selectedCategory]);

  useEffect(() => {
    if (authenticated) {
      fetchStatus();
      fetchReports();
      fetchFilterOptions();
    }
  }, [authenticated, fetchStatus, fetchReports, fetchFilterOptions]);

  // Reset and fetch when filters change
  useEffect(() => {
    if (authenticated && tab === 3) {
      setBrowsePoints([]);
      setBrowseOffset(0);
      setHasMorePoints(true);
      setSelectedPointIds(new Set()); // Clear selections
      fetchBrowsePoints(true);
    }
  }, [selectedSource, selectedCategory]);

  const handleDeletePoint = async () => {
    if (!pointToDelete) return;

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/point/${encodeURIComponent(pointToDelete.id)}`, {
        method: 'DELETE',
        headers: headers(),
      });
      if (res.ok) {
        // Remove the point from the list
        setBrowsePoints(prev => prev.filter(p => p.id !== pointToDelete.id));
        setSelectedPointIds(prev => {
          const next = new Set(prev);
          next.delete(pointToDelete.id);
          return next;
        });
        fetchStatus(); // Refresh the knowledge points count
      } else {
        const err = await res.json();
        setBrowseError(err.detail || 'Failed to delete knowledge point');
      }
    } catch {
      setBrowseError('Cannot delete knowledge point');
    } finally {
      setDeletePointConfirmOpen(false);
      setPointToDelete(null);
    }
  };

  const handleToggleSelect = (pointId: string) => {
    setSelectedPointIds(prev => {
      const next = new Set(prev);
      if (next.has(pointId)) {
        next.delete(pointId);
      } else {
        next.add(pointId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    if (selectedPointIds.size === browsePoints.length) {
      // Deselect all
      setSelectedPointIds(new Set());
    } else {
      // Select all
      setSelectedPointIds(new Set(browsePoints.map(p => p.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedPointIds.size === 0) return;

    setBulkDeleting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/points/delete`, {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ point_ids: Array.from(selectedPointIds) }),
      });
      if (res.ok) {
        const result = await res.json();
        // Remove deleted points from the list
        setBrowsePoints(prev => prev.filter(p => !selectedPointIds.has(p.id)));
        setSelectedPointIds(new Set());
        fetchStatus();
      } else {
        const err = await res.json();
        setBrowseError(err.detail || 'Failed to delete knowledge points');
      }
    } catch {
      setBrowseError('Cannot delete knowledge points');
    } finally {
      setBulkDeleting(false);
      setBulkDeleteConfirmOpen(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/status`, {
        headers: { 'X-Admin-Password': password },
      });
      if (res.ok) {
        setAuthenticated(true);
        setStatus(await res.json());
      } else {
        setAuthError('Invalid admin password');
      }
    } catch {
      setAuthError('Cannot connect to backend');
    }
  };

  const pollIngestionStatus = async (jobId: string) => {
    const maxAttempts = 120; // 10 minutes max (5s intervals)
    let attempts = 0;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/ingest/status/${jobId}`, {
          headers: headers(),
        });
        if (!res.ok) {
          throw new Error('Failed to get job status');
        }
        const status = await res.json();

        if (status.status === 'completed') {
          setIngestResult(status.result);
          setMarkdownText('');
          setFileName('');
          setIngesting(false);
          fetchStatus();
          return;
        } else if (status.status === 'failed') {
          setIngestError(status.error || 'Ingestion failed');
          setIngesting(false);
          return;
        }

        // Still running, poll again
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          setIngestError('Ingestion timed out - check backend logs');
          setIngesting(false);
        }
      } catch (err: any) {
        setIngestError(err.message);
        setIngesting(false);
      }
    };

    poll();
  };

  const handleIngestPaste = async () => {
    if (!markdownText.trim()) return;
    setIngesting(true);
    setIngestResult(null);
    setIngestError('');

    const name = fileName.trim() || `paste_${Date.now()}.md`;
    const finalName = name.endsWith('.md') ? name : `${name}.md`;
    const blob = new Blob([markdownText], { type: 'text/markdown' });
    const formData = new FormData();
    formData.append('file', blob, finalName);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/ingest`, {
        method: 'POST',
        headers: headers(),
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ingestion failed');
      }
      const result = await res.json();

      if (result.status === 'accepted' && result.job_id) {
        // Start polling for completion
        pollIngestionStatus(result.job_id);
      } else {
        // Synchronous completion (shouldn't happen with new code)
        setIngestResult(result);
        setMarkdownText('');
        setFileName('');
        setIngesting(false);
        fetchStatus();
      }
    } catch (err: any) {
      setIngestError(err.message);
      setIngesting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIngesting(true);
    setIngestResult(null);
    setIngestError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/ingest`, {
        method: 'POST',
        headers: headers(),
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Ingestion failed');
      }
      const result = await res.json();

      if (result.status === 'accepted' && result.job_id) {
        // Start polling for completion
        pollIngestionStatus(result.job_id);
      } else {
        setIngestResult(result);
        setIngesting(false);
        fetchStatus();
      }
    } catch (err: any) {
      setIngestError(err.message);
      setIngesting(false);
    } finally {
      e.target.value = '';
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);
    setSearchError('');

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/knowledge/search`, {
        method: 'POST',
        headers: {
          ...headers(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: searchQuery, limit: searchLimit }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Search failed');
      }
      const data = await res.json();
      setSearchResults(data.results);
    } catch (err: any) {
      setSearchError(err.message);
    } finally {
      setSearching(false);
    }
  };

  const handleViewReport = async (filename: string) => {
    setReportDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/cached-reports/${encodeURIComponent(filename)}`, {
        headers: headers(),
      });
      if (res.ok) {
        const detail = await res.json();
        setSelectedReport(detail);
      } else {
        const err = await res.json();
        setReportsError(err.detail || 'Failed to load report');
      }
    } catch {
      setReportsError('Cannot load report');
    } finally {
      setReportDetailLoading(false);
    }
  };

  const handleDeleteReport = async () => {
    if (!reportToDelete) return;

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/admin/cached-reports/${encodeURIComponent(reportToDelete)}`, {
        method: 'DELETE',
        headers: headers(),
      });
      if (res.ok) {
        fetchReports();
        if (selectedReport?.filename === reportToDelete) {
          setSelectedReport(null);
        }
      } else {
        const err = await res.json();
        setReportsError(err.detail || 'Failed to delete report');
      }
    } catch {
      setReportsError('Cannot delete report');
    } finally {
      setDeleteConfirmOpen(false);
      setReportToDelete(null);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const filteredReports = reports.filter(r =>
    r.address.toLowerCase().includes(reportFilter.toLowerCase())
  );

  // --- Login screen ---
  if (!authenticated) {
    return (
      <Box className="admin-login-container">
        <Box className="admin-login-box">
          <Lock sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Admin Portal
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Admin access required
          </Typography>

          <Paper elevation={3} sx={{ p: 4, width: '100%', maxWidth: 400 }}>
            {authError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {authError}
              </Alert>
            )}
            <form onSubmit={handleLogin}>
              <TextField
                fullWidth
                type="password"
                label="Admin Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                sx={{ mb: 2 }}
                autoFocus
              />
              <Button
                type="submit"
                variant="contained"
                fullWidth
                size="large"
                disabled={!password}
              >
                Sign In
              </Button>
            </form>
          </Paper>
        </Box>
      </Box>
    );
  }

  // --- Main UI with sidebar ---
  return (
    <Box className="admin-portal">
      {/* Sidebar */}
      <Drawer
        variant="permanent"
        sx={{
          width: SIDEBAR_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: SIDEBAR_WIDTH,
            boxSizing: 'border-box',
            bgcolor: '#1a1a2e',
            color: 'white',
          },
        }}
      >
        <Box sx={{ p: 2, borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Perchspot Admin
          </Typography>
        </Box>

        <List sx={{ flexGrow: 1 }}>
          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'knowledge'}
              onClick={() => setActiveSection('knowledge')}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <MenuBook />
              </ListItemIcon>
              <ListItemText primary="Knowledge Base" />
            </ListItemButton>
          </ListItem>

          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'reports'}
              onClick={() => setActiveSection('reports')}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <Assessment />
              </ListItemIcon>
              <ListItemText primary="Cached Reports" />
              {reports.length > 0 && (
                <Chip
                  label={reports.length}
                  size="small"
                  sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
                />
              )}
            </ListItemButton>
          </ListItem>

          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'promos'}
              onClick={() => { setActiveSection('promos'); fetchPromoCodes(); }}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <ContentPaste />
              </ListItemIcon>
              <ListItemText primary="Promo Codes" />
            </ListItemButton>
          </ListItem>

          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'users'}
              onClick={() => { setActiveSection('users'); fetchUsers(); }}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <People />
              </ListItemIcon>
              <ListItemText primary="Users" />
              {users.length > 0 && (
                <Chip
                  label={users.length}
                  size="small"
                  sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
                />
              )}
            </ListItemButton>
          </ListItem>

          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'surveys'}
              onClick={() => { setActiveSection('surveys'); fetchSurveys(); }}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <Feedback />
              </ListItemIcon>
              <ListItemText primary="Surveys" />
              {surveys.length > 0 && (
                <Chip
                  label={surveys.length}
                  size="small"
                  sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white' }}
                />
              )}
            </ListItemButton>
          </ListItem>

          <ListItem disablePadding>
            <ListItemButton
              selected={activeSection === 'analytics'}
              onClick={() => { setActiveSection('analytics'); fetchAnalyses(); fetchAnalysisStats(); }}
              sx={{
                '&.Mui-selected': { bgcolor: 'rgba(255,255,255,0.1)' },
                '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
              }}
            >
              <ListItemIcon sx={{ color: 'inherit' }}>
                <Analytics />
              </ListItemIcon>
              <ListItemText primary="Analytics" />
            </ListItemButton>
          </ListItem>
        </List>

        <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <Button
            startIcon={<Home />}
            onClick={() => navigate('/')}
            sx={{ color: 'rgba(255,255,255,0.7)', textTransform: 'none' }}
          >
            Back to Home
          </Button>
        </Box>
      </Drawer>

      {/* Main content */}
      <Box className="admin-content" sx={{ ml: `${SIDEBAR_WIDTH}px` }}>
        {/* Knowledge Base Section */}
        {activeSection === 'knowledge' && (
          <Box sx={{ p: 4 }}>
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h4">Knowledge Base</Typography>
                <Typography variant="body2" color="text.secondary">
                  Ingest and search knowledge for property analysis
                </Typography>
              </Box>
              {status && (
                <Chip
                  icon={<Storage />}
                  label={`${status.point_count} knowledge points`}
                  color={status.status === 'green' ? 'success' : 'warning'}
                  variant="outlined"
                />
              )}
            </Box>

            <Paper elevation={2}>
              <Tabs value={tab} onChange={(_, v) => {
                  setTab(v);
                  if (v === 3 && browsePoints.length === 0) {
                    fetchBrowsePoints(true);
                  }
                }} sx={{ borderBottom: 1, borderColor: 'divider' }}>
                <Tab icon={<ContentPaste />} label="Paste & Ingest" iconPosition="start" />
                <Tab icon={<Upload />} label="Upload File" iconPosition="start" />
                <Tab icon={<Search />} label="Search Test" iconPosition="start" />
                <Tab icon={<ListIcon />} label="Browse All" iconPosition="start" />
              </Tabs>

              <Box sx={{ p: 3 }}>
                {tab === 0 && (
                  <>
                    <TextField
                      fullWidth
                      label="Source Name (optional)"
                      placeholder="e.g. eastside_market_knowledge"
                      value={fileName}
                      onChange={(e) => setFileName(e.target.value)}
                      size="small"
                      sx={{ mb: 2 }}
                    />
                    <TextField
                      fullWidth
                      multiline
                      minRows={12}
                      maxRows={30}
                      label="Paste Markdown"
                      placeholder={`# Knowledge Title\n\n## 1. Category Name\nFirst knowledge point paragraph...\n\n## 2. Another Category\nThird knowledge point paragraph...`}
                      value={markdownText}
                      onChange={(e) => setMarkdownText(e.target.value)}
                      sx={{ mb: 2, fontFamily: 'monospace' }}
                      InputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
                    />
                    <Button
                      variant="contained"
                      onClick={handleIngestPaste}
                      disabled={ingesting || !markdownText.trim()}
                      startIcon={<ContentPaste />}
                    >
                      {ingesting ? 'Ingesting...' : 'Ingest Markdown'}
                    </Button>
                    {ingesting && <LinearProgress sx={{ mt: 2 }} />}
                  </>
                )}

                {tab === 1 && (
                  <>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      Upload a <code>.md</code> file with numbered category headings.
                      Each paragraph becomes one searchable knowledge point.
                    </Typography>
                    <Button
                      variant="contained"
                      component="label"
                      startIcon={<Upload />}
                      disabled={ingesting}
                    >
                      {ingesting ? 'Uploading...' : 'Choose .md File'}
                      <input
                        type="file"
                        accept=".md"
                        hidden
                        onChange={handleFileUpload}
                      />
                    </Button>
                    {ingesting && <LinearProgress sx={{ mt: 2 }} />}
                  </>
                )}

                {tab === 2 && (
                  <>
                    <form onSubmit={handleSearch}>
                      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                        <TextField
                          fullWidth
                          label="Search Query"
                          placeholder="e.g. school district ratings near Sammamish"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        <TextField
                          label="Limit"
                          type="number"
                          value={searchLimit}
                          onChange={(e) => setSearchLimit(Number(e.target.value))}
                          sx={{ width: 100 }}
                          inputProps={{ min: 1, max: 50 }}
                        />
                        <Button
                          type="submit"
                          variant="contained"
                          disabled={searching || !searchQuery.trim()}
                          startIcon={<Search />}
                          sx={{ minWidth: 120 }}
                        >
                          {searching ? 'Searching...' : 'Search'}
                        </Button>
                      </Box>
                    </form>
                    {searching && <LinearProgress />}
                    {searchError && <Alert severity="error" sx={{ mb: 2 }}>{searchError}</Alert>}
                    {searchResults.length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                          {searchResults.length} results
                        </Typography>
                        {searchResults.map((r, i) => (
                          <Card key={i} variant="outlined" sx={{ mb: 1 }}>
                            <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                                <Chip label={r.category} size="small" color="primary" variant="outlined" />
                                <Typography variant="caption" color="text.secondary">
                                  score: {r.score.toFixed(4)} | {r.source_file}
                                </Typography>
                              </Box>
                              <Typography variant="body2">{r.text}</Typography>
                            </CardContent>
                          </Card>
                        ))}
                      </Box>
                    )}
                  </>
                )}

                {/* Tab 3: Browse All */}
                {tab === 3 && (
                  <>
                    <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                      <FormControl sx={{ minWidth: 200 }} size="small">
                        <InputLabel>Filter by Source</InputLabel>
                        <Select
                          value={selectedSource}
                          label="Filter by Source"
                          onChange={(e) => setSelectedSource(e.target.value)}
                          startAdornment={<FilterList sx={{ mr: 1, color: 'action.active' }} />}
                        >
                          <MenuItem value="">
                            <em>All Sources</em>
                          </MenuItem>
                          {filterOptions.sources.map((source) => (
                            <MenuItem key={source} value={source}>
                              {source}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>

                      <FormControl sx={{ minWidth: 200 }} size="small">
                        <InputLabel>Filter by Category</InputLabel>
                        <Select
                          value={selectedCategory}
                          label="Filter by Category"
                          onChange={(e) => setSelectedCategory(e.target.value)}
                          startAdornment={<FilterList sx={{ mr: 1, color: 'action.active' }} />}
                        >
                          <MenuItem value="">
                            <em>All Categories</em>
                          </MenuItem>
                          {filterOptions.categories.map((category) => (
                            <MenuItem key={category} value={category}>
                              {category}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>

                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => {
                          setSelectedSource('');
                          setSelectedCategory('');
                        }}
                        disabled={!selectedSource && !selectedCategory}
                      >
                        Clear Filters
                      </Button>

                      <Box sx={{ flexGrow: 1 }} />

                      <Typography variant="body2" color="text.secondary">
                        {browsePoints.length} points loaded
                      </Typography>
                    </Box>

                    {/* Selection controls */}
                    {browsePoints.length > 0 && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={browsePoints.length > 0 && selectedPointIds.size === browsePoints.length}
                              indeterminate={selectedPointIds.size > 0 && selectedPointIds.size < browsePoints.length}
                              onChange={handleSelectAll}
                            />
                          }
                          label={`Select All (${browsePoints.length})`}
                        />
                        {selectedPointIds.size > 0 && (
                          <>
                            <Typography variant="body2" color="primary">
                              {selectedPointIds.size} selected
                            </Typography>
                            <Button
                              variant="contained"
                              color="error"
                              size="small"
                              startIcon={<Delete />}
                              onClick={() => setBulkDeleteConfirmOpen(true)}
                            >
                              Delete Selected
                            </Button>
                          </>
                        )}
                      </Box>
                    )}

                    {browseError && <Alert severity="error" sx={{ mb: 2 }}>{browseError}</Alert>}

                    {browseLoading && browsePoints.length === 0 ? (
                      <LinearProgress />
                    ) : (
                      <>
                        <Box sx={{ maxHeight: 'calc(100vh - 400px)', overflow: 'auto' }}>
                          {browsePoints.length === 0 ? (
                            <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                              No knowledge points found with the selected filters
                            </Typography>
                          ) : (
                            browsePoints.map((point, i) => (
                              <Card
                                key={point.id}
                                variant="outlined"
                                sx={{
                                  mb: 1,
                                  bgcolor: selectedPointIds.has(point.id) ? 'action.selected' : 'background.paper',
                                }}
                              >
                                <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                                    <Checkbox
                                      checked={selectedPointIds.has(point.id)}
                                      onChange={() => handleToggleSelect(point.id)}
                                      sx={{ p: 0, mt: 0.5 }}
                                    />
                                    <Box sx={{ flexGrow: 1 }}>
                                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                          <Chip label={point.category} size="small" color="primary" variant="outlined" />
                                          <Chip label={point.source_file} size="small" variant="outlined" />
                                        </Box>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                          <Typography variant="caption" color="text.secondary">
                                            #{i + 1}
                                          </Typography>
                                          <IconButton
                                            size="small"
                                            color="error"
                                            onClick={() => {
                                              setPointToDelete(point);
                                              setDeletePointConfirmOpen(true);
                                            }}
                                            sx={{ p: 0.5 }}
                                          >
                                            <Delete fontSize="small" />
                                          </IconButton>
                                        </Box>
                                      </Box>
                                      <Typography variant="body2" sx={{ mt: 1 }}>
                                        {point.text}
                                      </Typography>
                                    </Box>
                                  </Box>
                                </CardContent>
                              </Card>
                            ))
                          )}
                        </Box>

                        {hasMorePoints && browsePoints.length > 0 && (
                          <Box sx={{ textAlign: 'center', mt: 2 }}>
                            <Button
                              variant="outlined"
                              onClick={() => fetchBrowsePoints(false)}
                              disabled={browseLoading}
                            >
                              {browseLoading ? 'Loading...' : 'Load More'}
                            </Button>
                          </Box>
                        )}
                      </>
                    )}
                  </>
                )}

                {ingestResult && (
                  <Alert severity="success" sx={{ mt: 2 }} icon={<CheckCircle />}
                         onClose={() => setIngestResult(null)}>
                    Ingested <strong>{ingestResult.points_ingested}</strong> knowledge points
                    from <strong>{ingestResult.source_file}</strong>
                    {ingestResult.categories && (
                      <Box sx={{ mt: 1 }}>
                        Categories: {ingestResult.categories.map((c: string) => (
                          <Chip key={c} label={c} size="small" sx={{ mr: 0.5 }} />
                        ))}
                      </Box>
                    )}
                  </Alert>
                )}
                {ingestError && (
                  <Alert severity="error" sx={{ mt: 2 }} onClose={() => setIngestError('')}>
                    {ingestError}
                  </Alert>
                )}
              </Box>
            </Paper>
          </Box>
        )}

        {/* Cached Reports Section */}
        {activeSection === 'reports' && (
          <Box sx={{ p: 4 }}>
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h4">Cached Reports</Typography>
                <Typography variant="body2" color="text.secondary">
                  View and manage cached housing analysis reports
                </Typography>
              </Box>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={fetchReports}
                disabled={reportsLoading}
              >
                Refresh
              </Button>
            </Box>

            {reportsError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setReportsError('')}>
                {reportsError}
              </Alert>
            )}

            <Paper elevation={2}>
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="Filter by address..."
                  value={reportFilter}
                  onChange={(e) => setReportFilter(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Search />
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>

              {reportsLoading ? (
                <LinearProgress />
              ) : (
                <TableContainer sx={{ maxHeight: 'calc(100vh - 300px)' }}>
                  <Table stickyHeader>
                    <TableHead>
                      <TableRow>
                        <TableCell>Address</TableCell>
                        <TableCell>Modified</TableCell>
                        <TableCell>Size</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredReports.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                            <Typography color="text.secondary">
                              {reportFilter ? 'No reports match your filter' : 'No cached reports found'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredReports.map((report) => (
                          <TableRow
                            key={report.filename}
                            hover
                            sx={{ cursor: 'pointer' }}
                            onClick={() => handleViewReport(report.filename)}
                          >
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                {report.address}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {report.filename}
                              </Typography>
                            </TableCell>
                            <TableCell>{formatDate(report.modified)}</TableCell>
                            <TableCell>{formatBytes(report.size_bytes)}</TableCell>
                            <TableCell align="right">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleViewReport(report.filename);
                                }}
                              >
                                <Visibility />
                              </IconButton>
                              <IconButton
                                size="small"
                                color="error"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setReportToDelete(report.filename);
                                  setDeleteConfirmOpen(true);
                                }}
                              >
                                <Delete />
                              </IconButton>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
                <Typography variant="body2" color="text.secondary">
                  {filteredReports.length} of {reports.length} reports
                </Typography>
              </Box>
            </Paper>
          </Box>
        )}

        {/* Promo Codes Section */}
        {activeSection === 'promos' && (
          <Box sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom sx={{ mb: 3 }}>
              Promo Codes
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Create promo codes with bonus credits. Users can enter codes during registration or use the direct link.
            </Typography>

            {promosError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setPromosError('')}>
                {promosError}
              </Alert>
            )}

            {/* Create New Promo */}
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Create New Promo Code
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
                <TextField
                  label="Custom Code"
                  value={newPromoCustomCode}
                  onChange={(e) => setNewPromoCustomCode(e.target.value.toUpperCase())}
                  size="small"
                  sx={{ width: 140 }}
                  placeholder="e.g., PH10OFF"
                  helperText="Empty = auto-generate"
                  inputProps={{ style: { textTransform: 'uppercase' } }}
                />
                <TextField
                  label="Credit Amount ($)"
                  type="number"
                  value={newPromoAmount}
                  onChange={(e) => setNewPromoAmount(e.target.value)}
                  size="small"
                  sx={{ width: 130 }}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">$</InputAdornment>,
                  }}
                />
                <TextField
                  label="Max Uses"
                  type="number"
                  value={newPromoMaxUses}
                  onChange={(e) => setNewPromoMaxUses(e.target.value)}
                  size="small"
                  sx={{ width: 100 }}
                  helperText="Empty = unlimited"
                />
                <TextField
                  label="Expires On"
                  type="date"
                  value={newPromoExpiresDate}
                  onChange={(e) => setNewPromoExpiresDate(e.target.value)}
                  size="small"
                  sx={{ width: 160 }}
                  helperText="Empty = never"
                  InputLabelProps={{ shrink: true }}
                />
                <TextField
                  label="Note (optional)"
                  value={newPromoNote}
                  onChange={(e) => setNewPromoNote(e.target.value)}
                  size="small"
                  sx={{ width: 200 }}
                  placeholder="e.g., Product Hunt launch"
                />
                <Button
                  variant="contained"
                  onClick={createPromoCode}
                  disabled={creatingPromo || !newPromoAmount}
                  sx={{ height: 40 }}
                >
                  {creatingPromo ? 'Creating...' : 'Create Code'}
                </Button>
              </Box>
            </Paper>

            {/* Promo Codes List */}
            <Paper>
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6">
                  Existing Promo Codes
                </Typography>
                <Button startIcon={<Refresh />} onClick={fetchPromoCodes} size="small">
                  Refresh
                </Button>
              </Box>

              {promosLoading ? (
                <LinearProgress />
              ) : promoCodes.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Typography color="text.secondary">
                    No promo codes yet. Create one above!
                  </Typography>
                </Box>
              ) : (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Code</TableCell>
                        <TableCell>Credit</TableCell>
                        <TableCell>Uses</TableCell>
                        <TableCell>Note</TableCell>
                        <TableCell>Registration URL</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {promoCodes.map((promo) => (
                        <TableRow key={promo.code} sx={{ opacity: promo.is_active ? 1 : 0.5 }}>
                          <TableCell>
                            <Chip label={promo.code} size="small" sx={{ fontFamily: 'monospace' }} />
                          </TableCell>
                          <TableCell>${promo.credit_amount.toFixed(2)}</TableCell>
                          <TableCell>
                            {promo.uses_count} / {promo.max_uses ?? '∞'}
                          </TableCell>
                          <TableCell>{promo.note || '—'}</TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="body2"
                                sx={{
                                  maxWidth: 250,
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  fontFamily: 'monospace',
                                  fontSize: '0.75rem',
                                }}
                              >
                                {promo.registration_url}
                              </Typography>
                              <IconButton
                                size="small"
                                onClick={() => copyToClipboard(promo.registration_url, promo.code)}
                                color={copiedCode === promo.code ? 'success' : 'default'}
                              >
                                {copiedCode === promo.code ? <CheckCircle fontSize="small" /> : <ContentPaste fontSize="small" />}
                              </IconButton>
                            </Box>
                          </TableCell>
                          <TableCell>
                            {promo.is_active ? (
                              <Chip label="Active" color="success" size="small" />
                            ) : (
                              <Chip label="Inactive" size="small" />
                            )}
                          </TableCell>
                          <TableCell>
                            {promo.is_active && (
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => deactivatePromoCode(promo.code)}
                                title="Deactivate"
                              >
                                <Delete fontSize="small" />
                              </IconButton>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>
          </Box>
        )}

        {/* Users Section */}
        {activeSection === 'users' && (
          <Box sx={{ p: 4 }}>
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h4">Registered Users</Typography>
                <Typography variant="body2" color="text.secondary">
                  View all users and their purchase history
                </Typography>
              </Box>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={fetchUsers}
                disabled={usersLoading}
              >
                Refresh
              </Button>
            </Box>

            {/* Summary Cards */}
            {usersSummary && (
              <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
                <Card sx={{ flex: 1 }}>
                  <CardContent>
                    <Typography color="text.secondary" variant="body2">Total Users</Typography>
                    <Typography variant="h4">{usersSummary.total_users}</Typography>
                  </CardContent>
                </Card>
                <Card sx={{ flex: 1 }}>
                  <CardContent>
                    <Typography color="text.secondary" variant="body2">Users with Purchases</Typography>
                    <Typography variant="h4">{usersSummary.users_with_purchases}</Typography>
                  </CardContent>
                </Card>
                <Card sx={{ flex: 1, bgcolor: 'success.light' }}>
                  <CardContent>
                    <Typography color="success.contrastText" variant="body2">Total Revenue</Typography>
                    <Typography variant="h4" color="success.contrastText">
                      ${usersSummary.total_revenue.toFixed(2)}
                    </Typography>
                  </CardContent>
                </Card>
              </Box>
            )}

            {usersError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setUsersError('')}>
                {usersError}
              </Alert>
            )}

            <Paper elevation={2}>
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="Filter by email..."
                  value={userFilter}
                  onChange={(e) => setUserFilter(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <Search />
                      </InputAdornment>
                    ),
                  }}
                />
              </Box>

              {usersLoading ? (
                <LinearProgress />
              ) : (
                <TableContainer sx={{ maxHeight: 'calc(100vh - 400px)' }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Email</TableCell>
                        <TableCell align="right">Balance</TableCell>
                        <TableCell align="right">Purchased</TableCell>
                        <TableCell align="right">Credits Bought</TableCell>
                        <TableCell align="center">Purchases</TableCell>
                        <TableCell>Registered</TableCell>
                        <TableCell>Last Purchase</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {users
                        .filter(u => u.email.toLowerCase().includes(userFilter.toLowerCase()))
                        .map((user) => (
                          <TableRow key={user.id} hover>
                            <TableCell>
                              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                {user.email}
                              </Typography>
                            </TableCell>
                            <TableCell align="right">
                              <Chip
                                label={`$${user.credit_balance.toFixed(2)}`}
                                size="small"
                                color={user.credit_balance > 0 ? 'success' : 'default'}
                                variant="outlined"
                              />
                            </TableCell>
                            <TableCell align="right">
                              {user.total_purchased > 0 ? (
                                <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                                  ${user.total_purchased.toFixed(2)}
                                </Typography>
                              ) : (
                                <Typography variant="body2" color="text.secondary">—</Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              {user.total_credits_purchased > 0 ? (
                                <Typography variant="body2">
                                  {user.total_credits_purchased.toFixed(2)}
                                </Typography>
                              ) : (
                                <Typography variant="body2" color="text.secondary">—</Typography>
                              )}
                            </TableCell>
                            <TableCell align="center">
                              {user.purchase_count > 0 ? (
                                <Chip label={user.purchase_count} size="small" color="primary" />
                              ) : (
                                <Typography variant="body2" color="text.secondary">0</Typography>
                              )}
                            </TableCell>
                            <TableCell>
                              <Typography variant="body2" color="text.secondary">
                                {formatDate(user.created_at)}
                              </Typography>
                            </TableCell>
                            <TableCell>
                              {user.last_purchase_at ? (
                                <Typography variant="body2" color="text.secondary">
                                  {formatDate(user.last_purchase_at)}
                                </Typography>
                              ) : (
                                <Typography variant="body2" color="text.secondary">—</Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              <Button
                                size="small"
                                variant="outlined"
                                startIcon={<AttachMoney />}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setAddCreditsUser(user);
                                }}
                              >
                                Add Credits
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      {users.filter(u => u.email.toLowerCase().includes(userFilter.toLowerCase())).length === 0 && (
                        <TableRow>
                          <TableCell colSpan={8} align="center" sx={{ py: 4 }}>
                            <Typography color="text.secondary">
                              {userFilter ? 'No users match your filter' : 'No users found'}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
                <Typography variant="body2" color="text.secondary">
                  {users.filter(u => u.email.toLowerCase().includes(userFilter.toLowerCase())).length} of {users.length} users
                </Typography>
              </Box>
            </Paper>
          </Box>
        )}

        {/* Surveys Section */}
        {activeSection === 'surveys' && (
          <Box sx={{ p: 4 }}>
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h4">Survey Responses</Typography>
                <Typography variant="body2" color="text.secondary">
                  View user feedback from the credits page survey
                </Typography>
              </Box>
              <Button
                variant="outlined"
                startIcon={<Refresh />}
                onClick={fetchSurveys}
                disabled={surveysLoading}
              >
                Refresh
              </Button>
            </Box>

            {/* Summary Cards */}
            {surveysSummary && (
              <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
                <Card sx={{ minWidth: 150 }}>
                  <CardContent>
                    <Typography color="text.secondary" variant="body2">Total Responses</Typography>
                    <Typography variant="h4">{surveysSummary.total_responses}</Typography>
                  </CardContent>
                </Card>
                {surveysSummary.average_satisfaction && (
                  <Card sx={{ minWidth: 150 }}>
                    <CardContent>
                      <Typography color="text.secondary" variant="body2">Avg Satisfaction</Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="h4">{surveysSummary.average_satisfaction}</Typography>
                        <Star sx={{ color: 'warning.main' }} />
                      </Box>
                    </CardContent>
                  </Card>
                )}
                {surveysSummary.source_breakdown && Object.keys(surveysSummary.source_breakdown).length > 0 && (
                  <Card sx={{ flex: 1, minWidth: 250 }}>
                    <CardContent>
                      <Typography color="text.secondary" variant="body2" gutterBottom>How Users Found Us</Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {Object.entries(surveysSummary.source_breakdown).map(([source, count]) => (
                          <Chip
                            key={source}
                            label={`${source}: ${count}`}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </CardContent>
                  </Card>
                )}
              </Box>
            )}

            {surveysError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSurveysError('')}>
                {surveysError}
              </Alert>
            )}

            <Paper elevation={2}>
              {surveysLoading ? (
                <LinearProgress />
              ) : surveys.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Feedback sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography color="text.secondary">
                    No survey responses yet
                  </Typography>
                </Box>
              ) : (
                <TableContainer sx={{ maxHeight: 'calc(100vh - 400px)' }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>User</TableCell>
                        <TableCell>How Found Us</TableCell>
                        <TableCell align="center">Satisfaction</TableCell>
                        <TableCell>Feedback</TableCell>
                        <TableCell>Date</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {surveys.map((survey) => (
                        <TableRow
                          key={survey.id}
                          hover
                          onClick={() => setSelectedSurvey(survey)}
                          sx={{ cursor: 'pointer' }}
                        >
                          <TableCell>
                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                              {survey.user_email}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {survey.how_did_you_hear ? (
                              <Chip
                                label={survey.how_did_you_hear}
                                size="small"
                                variant="outlined"
                              />
                            ) : (
                              <Typography variant="body2" color="text.secondary">—</Typography>
                            )}
                          </TableCell>
                          <TableCell align="center">
                            {survey.satisfaction ? (
                              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                  {survey.satisfaction}
                                </Typography>
                                <Star sx={{ fontSize: 16, color: 'warning.main' }} />
                              </Box>
                            ) : (
                              <Typography variant="body2" color="text.secondary">—</Typography>
                            )}
                          </TableCell>
                          <TableCell sx={{ maxWidth: 300 }}>
                            {survey.improvements ? (
                              <Typography
                                variant="body2"
                                sx={{
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                }}
                                title={survey.improvements}
                              >
                                {survey.improvements}
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">—</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {formatDate(survey.created_at)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {surveys.length > 0 && (
                <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'grey.50' }}>
                  <Typography variant="body2" color="text.secondary">
                    {surveys.length} survey responses
                  </Typography>
                </Box>
              )}
            </Paper>
          </Box>
        )}

        {/* Survey Detail Dialog */}
        <Dialog open={!!selectedSurvey} onClose={() => setSelectedSurvey(null)} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            Survey Response
            <IconButton onClick={() => setSelectedSurvey(null)} size="small"><Close /></IconButton>
          </DialogTitle>
          <DialogContent dividers>
            {selectedSurvey && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">User</Typography>
                  <Typography variant="body1">{selectedSurvey.user_email}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">How did they find us</Typography>
                  <Typography variant="body1">{selectedSurvey.how_did_you_hear || '—'}</Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Satisfaction</Typography>
                  <Typography variant="body1">
                    {selectedSurvey.satisfaction ? `${selectedSurvey.satisfaction} / 5` : '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Feedback / Improvements</Typography>
                  <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', mt: 0.5 }}>
                    {selectedSurvey.improvements || '—'}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">Submitted</Typography>
                  <Typography variant="body1">{formatDate(selectedSurvey.created_at)}</Typography>
                </Box>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setSelectedSurvey(null)}>Close</Button>
          </DialogActions>
        </Dialog>

        {/* Analytics Section */}
        {activeSection === 'analytics' && (
          <Box sx={{ p: 4, width: '100%', boxSizing: 'border-box' }}>
            <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h4">Analysis Analytics</Typography>
                <Typography variant="body2" color="text.secondary">
                  Track analysis success rate, latency, and costs
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                <FormControl size="small" sx={{ minWidth: 120 }}>
                  <InputLabel>Time Range</InputLabel>
                  <Select
                    value={analysisDays}
                    label="Time Range"
                    onChange={(e) => {
                      setAnalysisDays(e.target.value as number);
                      setTimeout(() => { fetchAnalyses(); fetchAnalysisStats(); }, 0);
                    }}
                  >
                    <MenuItem value={1}>Last 24 hours</MenuItem>
                    <MenuItem value={7}>Last 7 days</MenuItem>
                    <MenuItem value={30}>Last 30 days</MenuItem>
                    <MenuItem value={90}>Last 90 days</MenuItem>
                  </Select>
                </FormControl>
                <Button
                  variant="outlined"
                  startIcon={<Refresh />}
                  onClick={() => { fetchAnalyses(); fetchAnalysisStats(); }}
                  disabled={analysesLoading}
                >
                  Refresh
                </Button>
              </Box>
            </Box>

            {/* Stats Cards */}
            {analysisStats && (
              <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
                <Card sx={{ minWidth: 140 }}>
                  <CardContent>
                    <Typography color="text.secondary" variant="body2">Total Analyses</Typography>
                    <Typography variant="h4">{analysisStats.total_analyses}</Typography>
                  </CardContent>
                </Card>
                <Card sx={{ minWidth: 140, bgcolor: 'success.light' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CheckCircleOutline sx={{ color: 'success.contrastText' }} />
                      <Typography color="success.contrastText" variant="body2">Success Rate</Typography>
                    </Box>
                    <Typography variant="h4" color="success.contrastText">
                      {analysisStats.success_rate}%
                    </Typography>
                  </CardContent>
                </Card>
                <Card sx={{ minWidth: 140 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Cached />
                      <Typography color="text.secondary" variant="body2">Cache Rate</Typography>
                    </Box>
                    <Typography variant="h4">{analysisStats.cache_rate}%</Typography>
                  </CardContent>
                </Card>
                <Card sx={{ minWidth: 140 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Timer />
                      <Typography color="text.secondary" variant="body2">Avg Duration</Typography>
                    </Box>
                    <Typography variant="h4">
                      {analysisStats.avg_duration_ms
                        ? `${(analysisStats.avg_duration_ms / 1000).toFixed(1)}s`
                        : 'N/A'}
                    </Typography>
                  </CardContent>
                </Card>
                <Card sx={{ minWidth: 140, bgcolor: 'primary.light' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AttachMoney sx={{ color: 'primary.contrastText' }} />
                      <Typography color="primary.contrastText" variant="body2">Total Cost</Typography>
                    </Box>
                    <Typography variant="h4" color="primary.contrastText">
                      ${analysisStats.total_cost.toFixed(2)}
                    </Typography>
                  </CardContent>
                </Card>
                {analysisStats.failed > 0 && (
                  <Card sx={{ minWidth: 140, bgcolor: 'error.light' }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <ErrorIcon sx={{ color: 'error.contrastText' }} />
                        <Typography color="error.contrastText" variant="body2">Failed</Typography>
                      </Box>
                      <Typography variant="h4" color="error.contrastText">
                        {analysisStats.failed}
                      </Typography>
                    </CardContent>
                  </Card>
                )}
              </Box>
            )}

            {analysesError && (
              <Alert severity="error" sx={{ mb: 2 }} onClose={() => setAnalysesError('')}>
                {analysesError}
              </Alert>
            )}

            {/* Analyses Table */}
            <Paper elevation={2} sx={{ width: '100%' }}>
              <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6">Recent Analyses</Typography>
                <Typography variant="body2" color="text.secondary">
                  {analyses.length} analyses
                </Typography>
              </Box>

              {analysesLoading ? (
                <LinearProgress />
              ) : analyses.length === 0 ? (
                <Box sx={{ p: 4, textAlign: 'center' }}>
                  <Analytics sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                  <Typography color="text.secondary">
                    No analyses found in the selected time range
                  </Typography>
                </Box>
              ) : (
                <TableContainer sx={{ maxHeight: 'calc(100vh - 350px)' }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Address</TableCell>
                        <TableCell>User</TableCell>
                        <TableCell align="center">Status</TableCell>
                        <TableCell align="center">Cached</TableCell>
                        <TableCell align="right">Duration</TableCell>
                        <TableCell align="right">Cost</TableCell>
                        <TableCell>Date</TableCell>
                        <TableCell align="right">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {analyses.map((analysis) => (
                        <TableRow
                          key={analysis.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => fetchAnalysisDetail(analysis.id)}
                        >
                          <TableCell>
                            <Typography
                              variant="body2"
                              sx={{
                                maxWidth: 300,
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                              title={analysis.address || 'Unknown'}
                            >
                              {analysis.address || 'Unknown'}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {analysis.user_email ? (
                              <Typography variant="body2">{analysis.user_email}</Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">Anonymous</Typography>
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              label={analysis.status}
                              size="small"
                              color={
                                analysis.status === 'completed' ? 'success' :
                                analysis.status === 'failed' ? 'error' :
                                analysis.status === 'in_progress' ? 'warning' : 'default'
                              }
                            />
                          </TableCell>
                          <TableCell align="center">
                            {analysis.is_cached ? (
                              <Cached sx={{ color: 'info.main', fontSize: 20 }} />
                            ) : (
                              <Typography variant="body2" color="text.secondary">-</Typography>
                            )}
                          </TableCell>
                          <TableCell align="right">
                            {analysis.total_duration_ms
                              ? `${(analysis.total_duration_ms / 1000).toFixed(1)}s`
                              : '-'}
                          </TableCell>
                          <TableCell align="right">
                            {analysis.total_cost_user
                              ? `$${analysis.total_cost_user.toFixed(4)}`
                              : '-'}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {formatDate(analysis.created_at)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                fetchAnalysisDetail(analysis.id);
                              }}
                            >
                              <Visibility fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Paper>
          </Box>
        )}
      </Box>

      {/* Report Detail Dialog */}
      <Dialog
        open={!!selectedReport}
        onClose={() => setSelectedReport(null)}
        maxWidth="lg"
        fullWidth
      >
        {selectedReport && (
          <>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h6">{selectedReport.address}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {selectedReport.filename}
                </Typography>
              </Box>
              <IconButton onClick={() => setSelectedReport(null)}>
                <Close />
              </IconButton>
            </DialogTitle>
            <DialogContent dividers>
              {reportDetailLoading ? (
                <LinearProgress />
              ) : (
                <Box>
                  {/* Scores Summary */}
                  {selectedReport.parsed.overall_score !== null && (
                    <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                      <Typography variant="h6" gutterBottom>
                        Overall Score: {selectedReport.parsed.overall_score}/100
                        {selectedReport.parsed.overall_grade && (
                          <Chip
                            label={`Grade ${selectedReport.parsed.overall_grade}`}
                            color="primary"
                            size="small"
                            sx={{ ml: 2 }}
                          />
                        )}
                      </Typography>

                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mt: 2 }}>
                        {Object.entries(selectedReport.parsed.scores).map(([key, value]) =>
                          value !== null && (
                            <Chip
                              key={key}
                              label={`${key.charAt(0).toUpperCase() + key.slice(1)}: ${value}`}
                              variant="outlined"
                            />
                          )
                        )}
                      </Box>

                      {selectedReport.parsed.recommendation && (
                        <Box sx={{ mt: 2 }}>
                          <Typography variant="subtitle2" color="text.secondary">
                            Recommendation
                          </Typography>
                          <Typography variant="body2">
                            {selectedReport.parsed.recommendation}
                          </Typography>
                        </Box>
                      )}
                    </Paper>
                  )}

                  {/* Raw Content */}
                  <Typography variant="subtitle2" gutterBottom>
                    Raw Report Content
                  </Typography>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 2,
                      bgcolor: 'grey.50',
                      maxHeight: 400,
                      overflow: 'auto',
                      fontFamily: 'monospace',
                      fontSize: 12,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {selectedReport.content}
                  </Paper>
                </Box>
              )}
            </DialogContent>
            <DialogActions>
              <Button
                color="error"
                startIcon={<Delete />}
                onClick={() => {
                  setReportToDelete(selectedReport.filename);
                  setDeleteConfirmOpen(true);
                }}
              >
                Delete Report
              </Button>
              <Button onClick={() => setSelectedReport(null)}>
                Close
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => {
          setDeleteConfirmOpen(false);
          setReportToDelete(null);
        }}
      >
        <DialogTitle>Delete Report?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this cached report? This action cannot be undone.
          </Typography>
          {reportToDelete && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {reportToDelete}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setDeleteConfirmOpen(false);
            setReportToDelete(null);
          }}>
            Cancel
          </Button>
          <Button color="error" variant="contained" onClick={handleDeleteReport}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Knowledge Point Confirmation Dialog */}
      <Dialog
        open={deletePointConfirmOpen}
        onClose={() => {
          setDeletePointConfirmOpen(false);
          setPointToDelete(null);
        }}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Delete Knowledge Point?</DialogTitle>
        <DialogContent>
          <Typography gutterBottom>
            Are you sure you want to delete this knowledge point? This action cannot be undone.
          </Typography>
          {pointToDelete && (
            <Paper variant="outlined" sx={{ p: 2, mt: 2, bgcolor: 'grey.50' }}>
              <Box sx={{ display: 'flex', gap: 0.5, mb: 1 }}>
                <Chip label={pointToDelete.category} size="small" color="primary" variant="outlined" />
                <Chip label={pointToDelete.source_file} size="small" variant="outlined" />
              </Box>
              <Typography variant="body2">
                {pointToDelete.text}
              </Typography>
            </Paper>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setDeletePointConfirmOpen(false);
            setPointToDelete(null);
          }}>
            Cancel
          </Button>
          <Button color="error" variant="contained" onClick={handleDeletePoint}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog
        open={bulkDeleteConfirmOpen}
        onClose={() => setBulkDeleteConfirmOpen(false)}
      >
        <DialogTitle>Delete {selectedPointIds.size} Knowledge Points?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete <strong>{selectedPointIds.size}</strong> selected knowledge points?
            This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkDeleteConfirmOpen(false)} disabled={bulkDeleting}>
            Cancel
          </Button>
          <Button
            color="error"
            variant="contained"
            onClick={handleBulkDelete}
            disabled={bulkDeleting}
          >
            {bulkDeleting ? 'Deleting...' : `Delete ${selectedPointIds.size} Points`}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Analysis Detail Dialog */}
      <Dialog
        open={!!selectedAnalysis}
        onClose={() => setSelectedAnalysis(null)}
        maxWidth="lg"
        fullWidth
      >
        {selectedAnalysis && (
          <>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h6">Analysis Details</Typography>
                <Typography variant="caption" color="text.secondary">
                  {selectedAnalysis.request_id}
                </Typography>
              </Box>
              <IconButton onClick={() => setSelectedAnalysis(null)}>
                <Close />
              </IconButton>
            </DialogTitle>
            <DialogContent dividers>
              {analysisDetailLoading ? (
                <LinearProgress />
              ) : (
                <Box>
                  {/* Overview */}
                  <Paper variant="outlined" sx={{ p: 2, mb: 3 }}>
                    <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                      Overview
                    </Typography>
                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Address</Typography>
                        <Typography variant="body1">{selectedAnalysis.address || 'Unknown'}</Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">User</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.user_email || `Anonymous (${selectedAnalysis.client_ip})`}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Status</Typography>
                        <Chip
                          label={selectedAnalysis.status}
                          size="small"
                          color={
                            selectedAnalysis.status === 'completed' ? 'success' :
                            selectedAnalysis.status === 'failed' ? 'error' : 'default'
                          }
                        />
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Cached</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.is_cached ? 'Yes' : 'No'}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Duration</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.total_duration_ms
                            ? `${(selectedAnalysis.total_duration_ms / 1000).toFixed(2)}s`
                            : 'N/A'}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Cost (User)</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.total_cost_user
                            ? `$${selectedAnalysis.total_cost_user.toFixed(4)}`
                            : 'N/A'}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Started</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.started_at ? formatDate(selectedAnalysis.started_at) : 'N/A'}
                        </Typography>
                      </Box>
                      <Box>
                        <Typography variant="body2" color="text.secondary">Completed</Typography>
                        <Typography variant="body1">
                          {selectedAnalysis.completed_at ? formatDate(selectedAnalysis.completed_at) : 'N/A'}
                        </Typography>
                      </Box>
                    </Box>

                    {selectedAnalysis.error_message && (
                      <Alert severity="error" sx={{ mt: 2 }}>
                        <Typography variant="body2">
                          <strong>Error at step {selectedAnalysis.error_step}:</strong> {selectedAnalysis.error_message}
                        </Typography>
                      </Alert>
                    )}
                  </Paper>

                  {/* Step Breakdown */}
                  <Typography variant="subtitle1" gutterBottom sx={{ fontWeight: 600 }}>
                    Step Breakdown
                  </Typography>
                  {selectedAnalysis.steps && selectedAnalysis.steps.length > 0 ? (
                    <TableContainer component={Paper} variant="outlined">
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>#</TableCell>
                            <TableCell>Step Name</TableCell>
                            <TableCell>Type</TableCell>
                            <TableCell align="center">Status</TableCell>
                            <TableCell align="right">Duration</TableCell>
                            <TableCell align="right">Cost</TableCell>
                            <TableCell align="right">Tokens</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {selectedAnalysis.steps.map((step: any) => (
                            <TableRow
                              key={step.id}
                              sx={{
                                bgcolor: step.status === 'failed' ? 'error.lighter' : 'inherit',
                              }}
                            >
                              <TableCell>{step.step_number}</TableCell>
                              <TableCell>{step.step_name}</TableCell>
                              <TableCell>
                                <Chip
                                  label={step.step_type}
                                  size="small"
                                  variant="outlined"
                                  color={
                                    step.step_type === 'analysis' ? 'primary' :
                                    step.step_type === 'extraction' ? 'secondary' : 'default'
                                  }
                                />
                              </TableCell>
                              <TableCell align="center">
                                <Chip
                                  label={step.status}
                                  size="small"
                                  color={
                                    step.status === 'completed' ? 'success' :
                                    step.status === 'failed' ? 'error' :
                                    step.status === 'skipped' ? 'default' : 'warning'
                                  }
                                />
                              </TableCell>
                              <TableCell align="right">
                                {step.duration_ms
                                  ? `${(Math.abs(step.duration_ms) / 1000).toFixed(2)}s`
                                  : '-'}
                              </TableCell>
                              <TableCell align="right">
                                {step.cost ? `$${step.cost.toFixed(4)}` : '-'}
                              </TableCell>
                              <TableCell align="right">
                                {step.input_tokens || step.output_tokens
                                  ? `${step.input_tokens || 0}/${step.output_tokens || 0}`
                                  : '-'}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No step data available
                    </Typography>
                  )}
                </Box>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setSelectedAnalysis(null)}>Close</Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Add Credits Dialog */}
      <Dialog
        open={!!addCreditsUser}
        onClose={() => {
          setAddCreditsUser(null);
          setAddCreditsAmount('');
          setAddCreditsReason('');
        }}
        maxWidth="sm"
        fullWidth
      >
        {addCreditsUser && (
          <>
            <DialogTitle>Add Credits to User</DialogTitle>
            <DialogContent>
              <Box sx={{ pt: 1 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  User: <strong>{addCreditsUser.email}</strong>
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Current Balance: <strong>${addCreditsUser.credit_balance.toFixed(2)}</strong>
                </Typography>

                <TextField
                  fullWidth
                  label="Amount to Add"
                  type="number"
                  value={addCreditsAmount}
                  onChange={(e) => setAddCreditsAmount(e.target.value)}
                  InputProps={{
                    startAdornment: <InputAdornment position="start">$</InputAdornment>,
                  }}
                  sx={{ mb: 2 }}
                  autoFocus
                />

                <TextField
                  fullWidth
                  label="Reason (optional)"
                  value={addCreditsReason}
                  onChange={(e) => setAddCreditsReason(e.target.value)}
                  placeholder="e.g., Refund, Promotional credit, etc."
                />
              </Box>
            </DialogContent>
            <DialogActions>
              <Button
                onClick={() => {
                  setAddCreditsUser(null);
                  setAddCreditsAmount('');
                  setAddCreditsReason('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={handleAddCredits}
                disabled={!addCreditsAmount || parseFloat(addCreditsAmount) <= 0 || addCreditsLoading}
              >
                {addCreditsLoading ? 'Adding...' : 'Add Credits'}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>
    </Box>
  );
}
