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
  const [activeSection, setActiveSection] = useState<'knowledge' | 'reports'>('reports');

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
    </Box>
  );
}
