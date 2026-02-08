import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  Container,
  Alert,
  Tabs,
  Tab,
  Chip,
  LinearProgress,
  Card,
  CardContent,
  IconButton,
  Divider,
} from '@mui/material';
import {
  Lock,
  Upload,
  Search,
  Storage,
  ContentPaste,
  CheckCircle,
  Delete,
} from '@mui/icons-material';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

export default function KnowledgeManagement() {
  const [password, setPassword] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [authError, setAuthError] = useState('');

  const [tab, setTab] = useState(0);
  const [status, setStatus] = useState<CollectionStatus | null>(null);

  // Ingest state
  const [markdownText, setMarkdownText] = useState('');
  const [fileName, setFileName] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<any>(null);
  const [ingestError, setIngestError] = useState('');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchLimit, setSearchLimit] = useState(10);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState('');

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

  useEffect(() => {
    if (authenticated) {
      fetchStatus();
    }
  }, [authenticated, fetchStatus]);

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
      setIngestResult(result);
      setMarkdownText('');
      setFileName('');
      fetchStatus();
    } catch (err: any) {
      setIngestError(err.message);
    } finally {
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
      setIngestResult(result);
      fetchStatus();
    } catch (err: any) {
      setIngestError(err.message);
    } finally {
      setIngesting(false);
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

  // --- Login screen ---
  if (!authenticated) {
    return (
      <Container maxWidth="sm">
        <Box sx={{ mt: 12, textAlign: 'center' }}>
          <Lock sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h4" gutterBottom>
            Knowledge Management
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            Admin access required
          </Typography>

          <Paper elevation={3} sx={{ p: 4 }}>
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
      </Container>
    );
  }

  // --- Main UI ---
  return (
    <Container maxWidth="lg">
      <Box sx={{ mt: 4, mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h4">Knowledge Management</Typography>
          <Typography variant="body2" color="text.secondary">
            Ingest and search knowledge for property analysis
          </Typography>
        </Box>
        {status && (
          <Box sx={{ textAlign: 'right' }}>
            <Chip
              icon={<Storage />}
              label={`${status.point_count} knowledge points`}
              color={status.status === 'green' ? 'success' : 'warning'}
              variant="outlined"
            />
          </Box>
        )}
      </Box>

      <Paper elevation={2}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab icon={<ContentPaste />} label="Paste & Ingest" iconPosition="start" />
          <Tab icon={<Upload />} label="Upload File" iconPosition="start" />
          <Tab icon={<Search />} label="Search Test" iconPosition="start" />
        </Tabs>

        <Box sx={{ p: 3 }}>
          {/* Tab 0: Paste & Ingest */}
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
                placeholder={`# Knowledge Title\n\n## 1. Category Name\nFirst knowledge point paragraph...\n\nSecond knowledge point paragraph...\n\n## 2. Another Category\nThird knowledge point paragraph...`}
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

          {/* Tab 1: Upload File */}
          {tab === 1 && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Upload a <code>.md</code> file with numbered category headings
                (<code>## 1. Category Name</code>). Each paragraph becomes one searchable knowledge point.
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

          {/* Tab 2: Search Test */}
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
              {!searching && searchResults.length === 0 && searchQuery && (
                <Typography variant="body2" color="text.secondary">
                  No results. Try a different query or ingest some knowledge first.
                </Typography>
              )}
            </>
          )}

          {/* Ingest result feedback (shown on any tab) */}
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
    </Container>
  );
}
