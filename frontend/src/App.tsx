import React, { useState, useEffect, useRef } from 'react';
import {
  UploadCloud, RefreshCw, CheckCircle, XCircle,
  AlertTriangle, User, Edit3, Building2, TrendingUp,
  FileSpreadsheet, ChevronRight, X, Sun, Moon,
  ChevronDown, Menu
} from 'lucide-react';

// Interfaces mapping to backend models
interface UserProfile {
  id: string;
  user: {
    id: number;
    username: string;
    email: string;
  };
  role: 'ANALYST' | 'AUDITOR' | 'ADMIN';
  tenant: string;
  tenant_name: string;
}

interface Facility {
  id: string;
  name: string;
  plant_code: string;
  country: string;
  region: string;
}

interface IngestionJob {
  id: string;
  source_type: 'SAP_FUEL_PROCUREMENT' | 'UTILITY_PORTAL_CSV' | 'CONCUR_TRAVEL';
  file_name: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  error_summary: string | null;
  uploaded_by_username: string;
  uploaded_at: string;
}

interface NormalizedRecord {
  id: string;
  facility: string | null;
  facility_name: string | null;
  scope: 1 | 2 | 3;
  category: string;
  activity_type: string;
  start_date: string;
  end_date: string;
  raw_quantity: string;
  raw_unit: string;
  normalized_quantity: string;
  normalized_unit: string;
  carbon_emissions_mtco2e: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  is_edited: boolean;
  rejection_reason: string | null;
  reviewed_by_username: string | null;
  reviewed_at: string | null;
  raw_data: any;
  raw_record_status: string;
  raw_record_error: string | null;
}

interface AuditLog {
  id: string;
  normalized_record: string;
  action: 'CREATE' | 'UPDATE' | 'APPROVE' | 'REJECT';
  field_name: string | null;
  old_value: string | null;
  new_value: string | null;
  changed_by_username: string;
  changed_at: string;
}

interface DashboardStats {
  total_emissions_mtco2e: number;
  pending_emissions_mtco2e: number;
  counts: {
    approved: number;
    pending: number;
    rejected: number;
    total: number;
  };
  scopes: {
    scope_1: number;
    scope_2: number;
    scope_3: number;
  };
  timeline: Array<{ month: string; emissions: number }>;
  trends?: {
    scope_1: number;
    scope_2: number;
    scope_3: number;
    overall: number;
  };
}

export default function App() {
  // Theme state
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const savedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    if (savedTheme === 'light' || savedTheme === 'dark') {
      return savedTheme;
    }
    // Auto-detect system OS preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.body.classList.add('dark-theme');
    } else {
      document.body.classList.remove('dark-theme');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  // Navigation & Sessions
  const [activeTab, setActiveTab] = useState<'dashboard' | 'ingest' | 'ledger'>('dashboard');
  const [mockUser, setMockUser] = useState<string>('acme_analyst');
  const [availableUsers, setAvailableUsers] = useState<UserProfile[]>([]);
  const [currentUserProfile, setCurrentUserProfile] = useState<UserProfile | null>(null);
  
  // Custom dropdown & mobile sidebar states
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [expandedJobIds, setExpandedJobIds] = useState<string[]>([]);
  
  // Data lists
  const [records, setRecords] = useState<NormalizedRecord[]>([]);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  // Filtering & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [filterScope, setFilterScope] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterFacility, setFilterFacility] = useState('');
  const [filterMonth, setFilterMonth] = useState('');

  // UI Selection States
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<NormalizedRecord | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Edit record states
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editQty, setEditQty] = useState('');
  const [editActivity, setEditActivity] = useState('');
  const [editFacility, setEditFacility] = useState('');
  const [editRecordId, setEditRecordId] = useState('');

  // Rejection reason dialog states
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [rejectionReasonInput, setRejectionReasonInput] = useState('');

  // Loading States
  const [uploadingSource, setUploadingSource] = useState<string | null>(null);

  // References for inputs
  const sapFileRef = useRef<HTMLInputElement>(null);
  const utilityFileRef = useRef<HTMLInputElement>(null);
  const travelFileRef = useRef<HTMLInputElement>(null);

  // Request Headers Helper
  const getHeaders = () => {
    return {
      'Content-Type': 'application/json',
      'X-Mock-User': mockUser
    };
  };

  // Fetch Session data & profiles
  useEffect(() => {
    fetch('/api/users/')
      .then(res => res.json())
      .then(data => setAvailableUsers(data))
      .catch(err => console.error("Error loading user profiles", err));
  }, []);

  // Fetch current user and reset data on mock user switch
  useEffect(() => {
    fetch(`/api/users/current/`, { headers: getHeaders() })
      .then(res => res.json())
      .then(profile => {
        setCurrentUserProfile(profile);
        // Refresh all data
        refreshData();
      })
      .catch(err => console.error("Error loading active profile", err));
  }, [mockUser]);

  const refreshData = () => {
    fetchDashboardStats();
    fetchIngestionJobs();
    fetchFacilities();
    fetchRecords();
    setIsDrawerOpen(false);
    setSelectedRecord(null);
    setSelectedIds([]);
  };

  const fetchRecords = () => {
    let url = `/api/normalized-records/?mock_user=${mockUser}`;
    if (filterScope) url += `&scope=${filterScope}`;
    if (filterCategory) url += `&category=${filterCategory}`;
    if (filterStatus) url += `&status=${filterStatus}`;
    if (filterFacility) url += `&facility=${filterFacility}`;
    if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;

    fetch(url, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => setRecords(data))
      .catch(err => console.error("Error loading ledger", err));
  };

  const fetchDashboardStats = () => {
    fetch(`/api/normalized-records/dashboard-stats/`, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(err => console.error("Error loading dashboard stats", err));
  };

  const fetchIngestionJobs = () => {
    fetch(`/api/ingest-jobs/`, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => setJobs(data.sort((a: any, b: any) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime())))
      .catch(err => console.error("Error loading jobs", err));
  };

  const fetchFacilities = () => {
    fetch(`/api/facilities/`, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => setFacilities(data))
      .catch(err => console.error("Error loading facilities", err));
  };

  const fetchAuditLogs = (recordId: string) => {
    fetch(`/api/audit-logs/?normalized_record=${recordId}`, { headers: getHeaders() })
      .then(res => res.json())
      .then(data => setAuditLogs(data))
      .catch(err => console.error("Error loading audit logs", err));
  };

  // Re-fetch records when filter / search changes
  useEffect(() => {
    fetchRecords();
  }, [filterScope, filterCategory, filterStatus, filterFacility, searchQuery]);

  // Handle file uploads
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>, sourceType: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingSource(sourceType);
    const formData = new FormData();
    formData.append('source_type', sourceType);
    formData.append('file', file);

    fetch('/api/ingest-jobs/upload/', {
      method: 'POST',
      headers: {
        'X-Mock-User': mockUser
      },
      body: formData
    })
      .then(async res => {
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error || "Ingestion request failed");
        }
        alert(`Ingestion Successful!\n${data.error_summary || 'File processed.'}`);
        refreshData();
      })
      .catch(err => {
        alert(`Ingestion failed: ${err.message}`);
        fetchIngestionJobs();
      })
      .finally(() => {
        setUploadingSource(null);
        // Clear input values
        if (sapFileRef.current) sapFileRef.current.value = '';
        if (utilityFileRef.current) utilityFileRef.current.value = '';
        if (travelFileRef.current) travelFileRef.current.value = '';
      });
  };

  // Record Drawer details click
  const handleRowClick = (record: NormalizedRecord) => {
    setSelectedRecord(record);
    setIsDrawerOpen(true);
    fetchAuditLogs(record.id);
  };

  // Single row approval / rejection
  const handleSingleReview = (actionType: 'approve' | 'reject', recordId: string) => {
    if (actionType === 'reject') {
      setSelectedIds([recordId]);
      setIsRejectModalOpen(true);
      return;
    }

    if (!confirm("Are you sure you want to approve and sign off on this record? This locks the record for audit.")) return;

    fetch('/api/normalized-records/bulk-action/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        action: 'approve',
        ids: [recordId]
      })
    })
      .then(res => res.json())
      .then(() => {
        alert("Record approved successfully.");
        refreshData();
      })
      .catch(err => console.error("Approval failed", err));
  };

  // Bulk reviews
  const handleBulkReview = (actionType: 'approve' | 'reject') => {
    if (selectedIds.length === 0) return;

    if (actionType === 'reject') {
      setIsRejectModalOpen(true);
      return;
    }

    if (!confirm(`Are you sure you want to approve ${selectedIds.length} records? This will lock them for audit.`)) return;

    fetch('/api/normalized-records/bulk-action/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        action: 'approve',
        ids: selectedIds
      })
    })
      .then(res => res.json())
      .then(() => {
        alert(`Approved ${selectedIds.length} records.`);
        refreshData();
      })
      .catch(err => console.error("Bulk approval failed", err));
  };

  const submitRejection = () => {
    if (!rejectionReasonInput.trim()) {
      alert("A rejection reason is required.");
      return;
    }

    fetch('/api/normalized-records/bulk-action/', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        action: 'reject',
        ids: selectedIds,
        rejection_reason: rejectionReasonInput
      })
    })
      .then(res => res.json())
      .then(() => {
        alert(`Rejected ${selectedIds.length} records.`);
        setIsRejectModalOpen(false);
        setRejectionReasonInput('');
        refreshData();
      })
      .catch(err => console.error("Bulk rejection failed", err));
  };

  // Open Edit Modal
  const openEditModal = (record: NormalizedRecord) => {
    setEditRecordId(record.id);
    setEditQty(record.raw_quantity);
    setEditActivity(record.activity_type);
    setEditFacility(record.facility || '');
    setIsEditModalOpen(true);
  };

  // Submit edits
  const saveRecordEdit = () => {
    if (!editQty || clean_decimal_check(editQty) <= 0) {
      alert("Please enter a valid positive quantity.");
      return;
    }

    fetch(`/api/normalized-records/${editRecordId}/`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify({
        raw_quantity: parseFloat(editQty),
        normalized_quantity: parseFloat(editQty),
        activity_type: editActivity,
        facility: editFacility || null
      })
    })
      .then(async res => {
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data[0] || data.detail || "Validation failed.");
        }
        alert("Record updated and emissions recalculated.");
        setIsEditModalOpen(false);
        refreshData();
      })
      .catch(err => {
        alert(`Update failed: ${err.message}`);
      });
  };

  // Check numeric quantity helper
  const clean_decimal_check = (val: string) => {
    try {
      return parseFloat(val);
    } catch {
      return 0;
    }
  };

  // Selection Checkbox handlers
  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      // Select pending items only from the currently filtered set
      const reviewable = filteredRecords.filter(r => r.status === 'PENDING').map(r => r.id);
      setSelectedIds(reviewable);
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectRow = (e: React.ChangeEvent<HTMLInputElement>, id: string) => {
    e.stopPropagation();
    if (e.target.checked) {
      setSelectedIds(prev => [...prev, id]);
    } else {
      setSelectedIds(prev => prev.filter(item => item !== id));
    }
  };

  // Custom visual values for Scope Pie simulation
  const getDonutStyle = () => {
    if (!stats) return { '--s1-pct': '0%', '--s2-pct': '0%' } as React.CSSProperties;
    const total = stats.scopes.scope_1 + stats.scopes.scope_2 + stats.scopes.scope_3;
    if (total === 0) return { '--s1-pct': '33%', '--s2-pct': '66%' } as React.CSSProperties;

    const s1 = Math.round((stats.scopes.scope_1 / total) * 100);
    const s2 = Math.round((stats.scopes.scope_2 / total) * 100);
    return {
      '--s1-pct': `${s1}%`,
      '--s2-pct': `${s1 + s2}%`
    } as React.CSSProperties;
  };

  // Custom timeline chart bar heights
  const getTimelineBarHeight = (emissions: number) => {
    if (!stats || stats.timeline.length === 0) return '0%';
    const maxVal = Math.max(...stats.timeline.map(t => t.emissions), 1);
    const pct = (emissions / maxVal) * 100;
    return `${Math.max(pct, 5)}%`; // min height 5% for visibility
  };

  // Display human-readable dates
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const toggleJobExpansion = (jobId: string) => {
    setExpandedJobIds(prev =>
      prev.includes(jobId) ? prev.filter(id => id !== jobId) : [...prev, jobId]
    );
  };

  const filteredRecords = records.filter(rec => {
    if (!filterMonth) return true;
    return rec.start_date.startsWith(filterMonth);
  });

  const selectedCarbonSum = filteredRecords
    .filter(r => selectedIds.includes(r.id))
    .reduce((sum, r) => sum + (parseFloat(r.carbon_emissions_mtco2e) || 0), 0);

  const filterByScope = (scopeVal: string) => {
    setFilterScope(scopeVal);
    setActiveTab('ledger');
  };

  const filterByMonth = (monthVal: string) => {
    setFilterMonth(monthVal);
    setActiveTab('ledger');
  };

  const filteredCarbonSum = filteredRecords.reduce((sum, r) => sum + (parseFloat(r.carbon_emissions_mtco2e) || 0), 0);
  const suspiciousCount = filteredRecords.filter(r => r.rejection_reason && r.status === 'PENDING').length;

  const handleClearFilters = () => {
    setSearchQuery('');
    setFilterScope('');
    setFilterCategory('');
    setFilterStatus('');
    setFilterFacility('');
    setFilterMonth('');
  };

  const handleExportAuditTrail = (record: NormalizedRecord) => {
    if (!record) return;
    
    let content = `BREATHE ESG AUDIT REPORT\n`;
    content += `====================================\n`;
    content += `Record ID: ${record.id}\n`;
    content += `Scope: Scope ${record.scope}\n`;
    content += `Category: ${record.category}\n`;
    content += `Activity Type: ${record.activity_type}\n`;
    content += `Carbon Emissions: ${parseFloat(record.carbon_emissions_mtco2e).toLocaleString(undefined, { minimumFractionDigits: 6 })} MT CO2e\n`;
    content += `Status: ${record.status}\n`;
    content += `Generated On: ${new Date().toLocaleString()}\n`;
    content += `====================================\n\n`;
    
    content += `IMMUTABLE AUDIT TRAIL LOGS:\n`;
    content += `------------------------------------\n`;
    if (auditLogs.length === 0) {
      content += `No changes logged for this record.\n`;
    } else {
      auditLogs.forEach((log, index) => {
        content += `[${index + 1}] Action: ${log.action}\n`;
        content += `    User: ${log.changed_by_username || 'System'}\n`;
        content += `    Timestamp: ${new Date(log.changed_at).toLocaleString()}\n`;
        if (log.field_name) {
          content += `    Field: ${log.field_name}\n`;
          content += `    Change: ${log.old_value || 'None'} ➔ ${log.new_value || 'None'}\n`;
        }
        content += `------------------------------------\n`;
      });
    }

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `audit_report_${record.id}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app-container">
      {/* Responsive mobile sidebar overlay backdrop */}
      {isMobileSidebarOpen && (
        <div className="sidebar-mobile-backdrop" onClick={() => setIsMobileSidebarOpen(false)} />
      )}

      {/* Persistent Side Navigation */}
      <aside className={`sidebar ${isMobileSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand-icon">B</div>
          <div>
            <h1 className="sidebar-brand-name">Breathe ESG</h1>
            <p className="sidebar-brand-subtitle">Carbon Management</p>
          </div>
        </div>

        <nav className="sidebar-menu">
          <button
            className={`sidebar-item ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => { setActiveTab('dashboard'); setIsMobileSidebarOpen(false); }}
          >
            <TrendingUp size={16} />
            <span>Overview</span>
          </button>
          <button
            className={`sidebar-item ${activeTab === 'ingest' ? 'active' : ''}`}
            onClick={() => { setActiveTab('ingest'); setIsMobileSidebarOpen(false); }}
          >
            <UploadCloud size={16} />
            <span>Ingest Hub</span>
          </button>
          <button
            className={`sidebar-item ${activeTab === 'ledger' ? 'active' : ''}`}
            onClick={() => { setActiveTab('ledger'); setIsMobileSidebarOpen(false); }}
          >
            <FileSpreadsheet size={16} />
            <span>Analyst Review</span>
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-tenant-card">
            <Building2 size={16} color="var(--color-primary)" />
            <div className="sidebar-tenant-info">
              <span className="sidebar-tenant-name" title={currentUserProfile?.tenant_name || 'Loading Tenant...'}>
                {currentUserProfile?.tenant_name || 'Loading Tenant...'}
              </span>
              <span className="sidebar-tenant-label">ACTIVE TENANT</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Workspace Column */}
      <div className="workspace-frame">
        {/* Topbar Header */}
        <header className="topbar">
          <div className="topbar-left" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '1rem' }}>
            {/* Hamburger menu toggle button for responsive sidebar */}
            <button
              className="mobile-menu-toggle"
              onClick={() => setIsMobileSidebarOpen(prev => !prev)}
              aria-label="Toggle Navigation Menu"
            >
              <Menu size={20} />
            </button>
            <div>
              <h2 className="topbar-title">
                {activeTab === 'dashboard' && 'Sustainability Performance'}
                {activeTab === 'ingest' && 'Data Feed Ingestion'}
                {activeTab === 'ledger' && 'Analyst Review Ledger'}
              </h2>
              <p className="topbar-subtitle">
                {activeTab === 'dashboard' && 'Calendar prorated scope emissions'}
                {activeTab === 'ingest' && 'Ingest CSV/JSON files from SAP, Utilities, and Travel'}
                {activeTab === 'ledger' && 'Verify and sign off on ingested emission records'}
              </p>
            </div>
          </div>

          <div className="topbar-right">
            {/* Theme Toggle Button */}
            <button
              onClick={() => setTheme(prev => (prev === 'light' ? 'dark' : 'light'))}
              className="theme-toggle-btn"
              title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
            >
              {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
            </button>

            {/* Mock Session Switcher */}
            <div className="session-switcher" style={{ border: 'none', padding: 0, background: 'none' }}>
              {/* Visually hidden native select to preserve automated Playwright test targets */}
              <select
                value={mockUser}
                onChange={(e) => setMockUser(e.target.value)}
                style={{ position: 'absolute', opacity: 0, width: 0, height: 0, pointerEvents: 'none' }}
              >
                {availableUsers.map(profile => (
                  <option key={profile.id} value={profile.user.username}>
                    {profile.user.username}
                  </option>
                ))}
              </select>

              {/* Custom Beautiful UI Dropdown */}
              <div className="custom-select-container">
                <button
                  className="custom-select-trigger"
                  onClick={() => setIsDropdownOpen(prev => !prev)}
                >
                  <User size={14} color="var(--color-scope2)" />
                  <span className="user-name-text">
                    {currentUserProfile ? currentUserProfile.user.username.replace('_', ' ').toUpperCase() : 'LOADING...'}
                  </span>
                  <span className="badge role-badge" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', marginLeft: '0.25rem', border: '1px solid currentColor' }}>
                    {currentUserProfile?.role}
                  </span>
                  <ChevronDown size={14} style={{ opacity: 0.7 }} />
                </button>

                {isDropdownOpen && (
                  <>
                    <div className="dropdown-backdrop" onClick={() => setIsDropdownOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 190 }} />
                    <div className="custom-select-options">
                      {availableUsers.map(profile => {
                        const isActive = profile.user.username === mockUser;
                        return (
                          <div
                            key={profile.id}
                            className={`custom-select-option ${isActive ? 'active' : ''}`}
                            onClick={() => {
                              setMockUser(profile.user.username);
                              setIsDropdownOpen(false);
                            }}
                          >
                            <span>{profile.user.username.replace('_', ' ').toUpperCase()}</span>
                            <span className="badge" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem', border: '1px solid currentColor' }}>
                              {profile.role}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="main-content">
        
        {/* VIEW 1: Dashboard Overview */}
        {activeTab === 'dashboard' && stats && (
          <>
            {/* KPI Cards Grid */}
            <div className="kpi-grid">
              <div className="kpi-card scope-1" onClick={() => filterByScope('1')} style={{ cursor: 'pointer' }}>
                <span className="kpi-title">Scope 1 (Direct Fuels)</span>
                <div className="kpi-value">
                  {stats.scopes.scope_1.toLocaleString()} <span className="kpi-unit">MT CO₂e</span>
                </div>
                <div className="kpi-footer">
                  <span>
                    {stats.trends && stats.trends.scope_1 !== 0 ? (
                      <span style={{ color: stats.trends.scope_1 > 0 ? 'var(--color-danger)' : 'var(--color-success)', fontWeight: 650 }}>
                        {stats.trends.scope_1 > 0 ? `+${stats.trends.scope_1}%` : `${stats.trends.scope_1}%`} MoM
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Stable MoM</span>
                    )}
                  </span>
                  <span className="badge scope1">Scope 1</span>
                </div>
              </div>
              <div className="kpi-card scope-2" onClick={() => filterByScope('2')} style={{ cursor: 'pointer' }}>
                <span className="kpi-title">Scope 2 (Electricity)</span>
                <div className="kpi-value">
                  {stats.scopes.scope_2.toLocaleString()} <span className="kpi-unit">MT CO₂e</span>
                </div>
                <div className="kpi-footer">
                  <span>
                    {stats.trends && stats.trends.scope_2 !== 0 ? (
                      <span style={{ color: stats.trends.scope_2 > 0 ? 'var(--color-danger)' : 'var(--color-success)', fontWeight: 650 }}>
                        {stats.trends.scope_2 > 0 ? `+${stats.trends.scope_2}%` : `${stats.trends.scope_2}%`} MoM
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Stable MoM</span>
                    )}
                  </span>
                  <span className="badge scope2">Scope 2</span>
                </div>
              </div>
              <div className="kpi-card scope-3" onClick={() => filterByScope('3')} style={{ cursor: 'pointer' }}>
                <span className="kpi-title">Scope 3 (Travel & Lodging)</span>
                <div className="kpi-value">
                  {stats.scopes.scope_3.toLocaleString()} <span className="kpi-unit">MT CO₂e</span>
                </div>
                <div className="kpi-footer">
                  <span>
                    {stats.trends && stats.trends.scope_3 !== 0 ? (
                      <span style={{ color: stats.trends.scope_3 > 0 ? 'var(--color-danger)' : 'var(--color-success)', fontWeight: 650 }}>
                        {stats.trends.scope_3 > 0 ? `+${stats.trends.scope_3}%` : `${stats.trends.scope_3}%`} MoM
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Stable MoM</span>
                    )}
                  </span>
                  <span className="badge scope3">Scope 3</span>
                </div>
              </div>
              <div className="kpi-card pending" onClick={() => { setFilterStatus('PENDING'); setActiveTab('ledger'); }} style={{ cursor: 'pointer' }}>
                <span className="kpi-title">Pending Approvals</span>
                <div className="kpi-value" style={{ color: 'var(--color-warning)' }}>
                  {stats.pending_emissions_mtco2e.toLocaleString()} <span className="kpi-unit">MT CO₂e</span>
                </div>
                <div className="kpi-footer">
                  <span>{stats.counts.pending} rows in pipeline</span>
                  <span className="badge warning">Pending</span>
                </div>
              </div>
            </div>

            {/* Visual Charts Section */}
            <div className="charts-section">
              {/* Timeline Chart */}
              <div className="chart-wrapper">
                <div className="card-title-bar">
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Emissions Timeline (Calendar Prorated)</h3>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Prorated Monthly Shares (MT CO₂e)</span>
                </div>
                {stats.timeline.length === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    No approved data to display timeline. Approve rows in the Review Ledger.
                  </div>
                ) : (
                  <div className="custom-bar-chart">
                    {stats.timeline.map((item, idx) => (
                      <div className="chart-bar-container" key={idx}>
                        <div
                          className="chart-bar"
                          style={{ height: getTimelineBarHeight(item.emissions), cursor: 'pointer' }}
                          onClick={() => filterByMonth(item.month)}
                        >
                          <div className="chart-bar-tooltip">
                            {item.emissions} MT CO₂e
                          </div>
                        </div>
                        <span className="chart-bar-label">
                          {new Date(item.month + '-02').toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Scopes Doughnut Simulation */}
              <div className="chart-wrapper">
                <div className="card-title-bar">
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Approved Carbon Mix by Scope</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {stats.trends && stats.trends.overall !== 0 && (
                      <span className={`badge ${stats.trends.overall > 0 ? 'danger' : 'success'}`} style={{ fontSize: '0.7rem', padding: '0.15rem 0.4rem', textTransform: 'none' }}>
                        {stats.trends.overall > 0 ? `+${stats.trends.overall}%` : `${stats.trends.overall}%`} MoM
                      </span>
                    )}
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Total: {stats.total_emissions_mtco2e.toLocaleString()} MT CO₂e</span>
                  </div>
                </div>
                {stats.total_emissions_mtco2e === 0 ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                    No approved emissions to display proportions.
                  </div>
                ) : (
                  <div className="donut-simulator">
                    <div className="donut-visual" style={getDonutStyle()}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '1.25rem', fontWeight: 800, fontFamily: 'var(--font-heading)' }}>
                          {stats.total_emissions_mtco2e.toLocaleString()}
                        </div>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>MT CO₂e</div>
                      </div>
                    </div>

                    <div className="donut-label-list">
                      <div className="donut-label-item" onClick={() => filterByScope('1')} style={{ cursor: 'pointer' }}>
                        <div className="donut-color-box" style={{ backgroundColor: 'var(--color-scope1)' }}></div>
                        <div>
                          <p style={{ fontWeight: 600 }}>Scope 1</p>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {stats.scopes.scope_1} MT ({Math.round((stats.scopes.scope_1 / stats.total_emissions_mtco2e)*100)}%)
                          </p>
                        </div>
                      </div>
                      <div className="donut-label-item" onClick={() => filterByScope('2')} style={{ cursor: 'pointer' }}>
                        <div className="donut-color-box" style={{ backgroundColor: 'var(--color-scope2)' }}></div>
                        <div>
                          <p style={{ fontWeight: 600 }}>Scope 2</p>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {stats.scopes.scope_2} MT ({Math.round((stats.scopes.scope_2 / stats.total_emissions_mtco2e)*100)}%)
                          </p>
                        </div>
                      </div>
                      <div className="donut-label-item" onClick={() => filterByScope('3')} style={{ cursor: 'pointer' }}>
                        <div className="donut-color-box" style={{ backgroundColor: 'var(--color-scope3)' }}></div>
                        <div>
                          <p style={{ fontWeight: 600 }}>Scope 3</p>
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {stats.scopes.scope_3} MT ({Math.round((stats.scopes.scope_3 / stats.total_emissions_mtco2e)*100)}%)
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Summary Section */}
            <div className="panel-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Review Pipeline Health</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
                Breathe ESG normalized ledger is currently managing <strong>{stats.counts.total} records</strong>. There are <strong>{stats.counts.pending} records pending sign-off</strong> representing <strong>{stats.pending_emissions_mtco2e} MT CO₂e</strong> of emissions awaiting validation. Approving rows will lock them permanently into the immutable audit mix shown above.
              </p>
            </div>
          </>
        )}

        {/* VIEW 2: Ingest Hub Panel */}
        {activeTab === 'ingest' && (
          <div className="ingest-section">
            {/* Upload zones */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="panel-card">
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>Upload Ingestion Feeds</h3>
                <div className="dropzone-container">
                  {/* SAP Fuel Upload */}
                  <div className={`dropzone ${uploadingSource === 'SAP_FUEL_PROCUREMENT' ? 'active' : ''}`}>
                    <UploadCloud size={24} color="var(--color-scope1)" />
                    <span className="dropzone-label">SAP Goods Movement CSV (Scope 1)</span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Supports MBLNR, BUDAT, WERKS, MATNR, MENGE, MEINS</span>
                    <input
                      type="file"
                      accept=".csv"
                      ref={sapFileRef}
                      className="dropzone-file-input"
                      onChange={(e) => handleFileUpload(e, 'SAP_FUEL_PROCUREMENT')}
                      disabled={uploadingSource !== null}
                    />
                  </div>

                  {/* Utility Electricity Upload */}
                  <div className={`dropzone ${uploadingSource === 'UTILITY_PORTAL_CSV' ? 'active' : ''}`}>
                    <UploadCloud size={24} color="var(--color-scope2)" />
                    <span className="dropzone-label">Utility Electricity Portal CSV (Scope 2)</span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Supports Account ID, Meter Number, Start Date, End Date, kWh</span>
                    <input
                      type="file"
                      accept=".csv"
                      ref={utilityFileRef}
                      className="dropzone-file-input"
                      onChange={(e) => handleFileUpload(e, 'UTILITY_PORTAL_CSV')}
                      disabled={uploadingSource !== null}
                    />
                  </div>

                  {/* Corporate Travel Upload */}
                  <div className={`dropzone ${uploadingSource === 'CONCUR_TRAVEL' ? 'active' : ''}`}>
                    <UploadCloud size={24} color="var(--color-scope3)" />
                    <span className="dropzone-label">Corporate Travel Export CSV (Scope 3)</span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Supports Flight IATA codes, Hotel Nights/Country, Car mileage</span>
                    <input
                      type="file"
                      accept=".csv"
                      ref={travelFileRef}
                      className="dropzone-file-input"
                      onChange={(e) => handleFileUpload(e, 'CONCUR_TRAVEL')}
                      disabled={uploadingSource !== null}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Ingest history logs */}
            <div className="panel-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div className="card-title-bar">
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Ingestion Logs & Stream Status</h3>
                <button className="btn btn-secondary" style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }} onClick={fetchIngestionJobs}>
                  <RefreshCw size={12} /> Refresh
                </button>
              </div>
              <div className="job-log-list">
                {jobs.length === 0 ? (
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem', fontSize: '0.9rem' }}>
                    No ingestion jobs run yet. Select a CSV feed on the left to start.
                  </div>
                ) : (
                  jobs.map((job) => (
                    <div className="job-log-item" key={job.id}>
                      <div className="job-log-details">
                        <span className="job-log-file">{job.file_name}</span>
                        <span className="job-log-meta">
                          Source: {job.source_type.replace('_', ' ')} | By: {job.uploaded_by_username} | {new Date(job.uploaded_at).toLocaleString()}
                        </span>
                        {job.error_summary && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', marginTop: '0.25rem' }}>
                            <button
                              onClick={() => toggleJobExpansion(job.id)}
                              className="btn btn-secondary"
                              style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', width: 'fit-content' }}
                            >
                              {expandedJobIds.includes(job.id) ? 'Hide Parse Log' : 'View Parse Log'}
                            </button>
                            {expandedJobIds.includes(job.id) && (
                              <pre style={{
                                background: 'var(--bg-lowest)',
                                border: '1px solid var(--border-color)',
                                borderRadius: '6px',
                                padding: '0.5rem',
                                fontSize: '0.75rem',
                                overflowX: 'auto',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-all',
                                fontFamily: 'var(--font-mono)',
                                color: 'var(--text-secondary)',
                                marginTop: '0.5rem',
                                maxWidth: '100%'
                              }}>
                                {job.error_summary}
                              </pre>
                            )}
                          </div>
                        )}
                      </div>
                      <span className={`badge ${job.status === 'COMPLETED' ? 'success' : job.status === 'FAILED' ? 'danger' : 'pending'}`}>
                        {job.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* VIEW 3: Analyst Review Ledger */}
        {activeTab === 'ledger' && (
          <>
            {/* Filter Bar */}
            <div className="ledger-header">
              <div className="filters-bar">
                <input
                  type="text"
                  placeholder="Search Activity..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="search-input"
                />
                
                <select className="filter-select" value={filterScope} onChange={(e) => setFilterScope(e.target.value)}>
                  <option value="">All Scopes</option>
                  <option value="1">Scope 1</option>
                  <option value="2">Scope 2</option>
                  <option value="3">Scope 3</option>
                </select>

                <select className="filter-select" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
                  <option value="">All Categories</option>
                  <option value="FUEL">Fuel Combustion</option>
                  <option value="ELECTRICITY">Purchased Electricity</option>
                  <option value="FLIGHT">Flights</option>
                  <option value="HOTEL">Hotels</option>
                  <option value="GROUND_TRANSPORT">Ground Transport</option>
                </select>

                <select className="filter-select" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                  <option value="">All Statuses</option>
                  <option value="PENDING">Pending Review</option>
                  <option value="APPROVED">Approved & Locked</option>
                  <option value="REJECTED">Rejected</option>
                </select>

                <select className="filter-select" value={filterFacility} onChange={(e) => setFilterFacility(e.target.value)}>
                  <option value="">All Facilities</option>
                  {facilities.map(f => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>

                {/* Clear Filters Button */}
                {(searchQuery || filterScope || filterCategory || filterStatus || filterFacility || filterMonth) && (
                  <button
                    onClick={handleClearFilters}
                    className="btn btn-secondary"
                    style={{ padding: '0.6rem 1rem', fontSize: '0.9rem', color: 'var(--color-danger)', borderColor: 'rgba(239, 68, 68, 0.2)' }}
                  >
                    Clear Filters
                  </button>
                )}
              </div>

              {/* Bulk actions drawer trigger */}
              {selectedIds.length > 0 && currentUserProfile?.role === 'ANALYST' && (
                <div className="bulk-actions">
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {selectedIds.length} Selected ({selectedCarbonSum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MT CO₂e)
                  </span>
                  <button className="btn btn-success" style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }} onClick={() => handleBulkReview('approve')}>
                    <CheckCircle size={12} /> Bulk Approve
                  </button>
                  <button className="btn btn-danger" style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }} onClick={() => handleBulkReview('reject')}>
                    <XCircle size={12} /> Bulk Reject
                  </button>
                </div>
              )}
            </div>

            {/* Filtered Context Summary Banner */}
            <div 
              className="ledger-summary-banner"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.75rem 1.25rem',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                fontSize: '0.85rem',
                color: 'var(--text-secondary)',
                boxShadow: 'var(--glass-shadow)',
                flexWrap: 'wrap',
                gap: '0.5rem',
                marginBottom: '1rem'
              }}
            >
              <div>
                Showing <strong>{filteredRecords.length}</strong> of <strong>{records.length}</strong> records 
                {filterMonth && <span> for month <strong>{filterMonth}</strong></span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
                <span>Filtered Sum: <strong style={{ color: 'var(--text-primary)' }}>{filteredCarbonSum.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 })}</strong> MT CO₂e</span>
                {suspiciousCount > 0 && (
                  <span className="badge warning" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.7rem' }}>
                    <AlertTriangle size={10} /> {suspiciousCount} Suspicious Flagged
                  </span>
                )}
              </div>
            </div>

            {/* Table Grid */}
            <div className="table-container">
              <table className="ledger-table">
                <thead>
                  <tr>
                    {currentUserProfile?.role === 'ANALYST' && (
                      <th style={{ width: '40px', paddingLeft: '1.25rem' }}>
                        <input
                          type="checkbox"
                          onChange={handleSelectAll}
                          checked={filteredRecords.length > 0 && selectedIds.length === filteredRecords.filter(r => r.status === 'PENDING').length}
                        />
                      </th>
                    )}
                    <th>Activity Period</th>
                    <th>Scope</th>
                    <th>Category</th>
                    <th>Activity Type</th>
                    <th>Facility</th>
                    <th>Raw Quantity</th>
                    <th>Normalized Qty</th>
                    <th>Emissions</th>
                    <th>Status</th>
                    <th>Lineage</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.length === 0 ? (
                    <tr>
                      <td colSpan={currentUserProfile?.role === 'ANALYST' ? 11 : 10} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                        No records match current filter criteria. Go to Ingest Hub to upload feeds.
                      </td>
                    </tr>
                  ) : (
                    filteredRecords.map((rec) => {
                      const isSelected = selectedIds.includes(rec.id);
                      const isSuspicious = rec.rejection_reason && rec.status === 'PENDING';
                      
                      return (
                        <tr
                          key={rec.id}
                          className={`${isSelected ? 'selected' : ''} ${isSuspicious ? 'suspicious' : ''}`}
                          onClick={() => handleRowClick(rec)}
                        >
                          {currentUserProfile?.role === 'ANALYST' && (
                            <td style={{ paddingLeft: '1.25rem' }} onClick={(e) => e.stopPropagation()}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                disabled={rec.status === 'APPROVED'}
                                onChange={(e) => handleSelectRow(e, rec.id)}
                              />
                            </td>
                          )}
                          <td>
                            {rec.start_date === rec.end_date ? (
                              formatDate(rec.start_date)
                            ) : (
                              `${formatDate(rec.start_date)} - ${formatDate(rec.end_date)}`
                            )}
                          </td>
                          <td>
                            <span className={`badge scope${rec.scope}`}>
                              Scope {rec.scope}
                            </span>
                          </td>
                          <td>{rec.category}</td>
                          <td>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                              {rec.activity_type}
                              {rec.is_edited && (
                                <span style={{ fontSize: '0.65rem', background: '#374151', color: '#9ca3af', padding: '0.1rem 0.3rem', borderRadius: '3px', fontWeight: 600 }}>
                                  EDITED
                                </span>
                              )}
                            </div>
                          </td>
                          <td>
                            {rec.facility_name ? (
                              <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.85rem' }}>
                                <Building2 size={12} color="var(--text-secondary)" /> {rec.facility_name}
                              </span>
                            ) : (
                              <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Global Organization</span>
                            )}
                          </td>
                          <td style={{ color: 'var(--text-secondary)' }}>
                            {parseFloat(rec.raw_quantity).toLocaleString()} {rec.raw_unit}
                          </td>
                          <td>
                            {parseFloat(rec.normalized_quantity).toLocaleString()} {rec.normalized_unit}
                          </td>
                          <td className="carbon-val" style={{ color: rec.status === 'APPROVED' ? 'var(--color-success)' : 'var(--text-primary)' }}>
                            {parseFloat(rec.carbon_emissions_mtco2e).toLocaleString(undefined, { minimumFractionDigits: 4 })}
                          </td>
                          <td>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                              <span className={`badge ${rec.status === 'APPROVED' ? 'success' : rec.status === 'REJECTED' ? 'danger' : 'pending'}`}>
                                {rec.status}
                              </span>
                              {isSuspicious && (
                                <span style={{ fontSize: '0.65rem', color: 'var(--color-warning)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.15rem' }}>
                                  <AlertTriangle size={10} /> SUSPICIOUS
                                </span>
                              )}
                            </div>
                          </td>
                          <td>
                            <ChevronRight size={16} color="var(--text-muted)" />
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
      </div> {/* Closing .workspace-frame */}

      {/* Slide-over Audit Detail Drawer */}
      <div className={`audit-drawer-overlay ${isDrawerOpen ? 'open' : ''}`} onClick={() => setIsDrawerOpen(false)}>
        <div className="audit-drawer" onClick={(e) => e.stopPropagation()}>
          <div className="drawer-header">
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Emissions Record Lineage</h2>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>ID: {selectedRecord?.id}</span>
            </div>
            <button className="drawer-close" onClick={() => setIsDrawerOpen(false)}>
              <X size={20} />
            </button>
          </div>

          {selectedRecord && (
            <div className="drawer-body">
              {/* Record Summary */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div>
                  <h3 style={{ fontSize: '1.4rem', fontWeight: 800 }}>
                    {parseFloat(selectedRecord.carbon_emissions_mtco2e).toLocaleString(undefined, { minimumFractionDigits: 6 })}
                  </h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 600, marginTop: '0.15rem' }}>Metric Tons CO₂e</p>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.4rem' }}>
                  <span className={`badge scope${selectedRecord.scope}`}>Scope {selectedRecord.scope}</span>
                  <span className={`badge ${selectedRecord.status === 'APPROVED' ? 'success' : selectedRecord.status === 'REJECTED' ? 'danger' : 'pending'}`}>
                    {selectedRecord.status}
                  </span>
                </div>
              </div>

              {/* Mappings & Dates */}
              <div>
                <p className="drawer-section-title">Ingestion Metadata</p>
                <div className="meta-details-grid">
                  <div className="meta-detail-item">
                    <span className="meta-detail-label">Facility</span>
                    <span className="meta-detail-value">{selectedRecord.facility_name || 'Global Organization'}</span>
                  </div>
                  <div className="meta-detail-item">
                    <span className="meta-detail-label">Activity Category</span>
                    <span className="meta-detail-value">{selectedRecord.category}</span>
                  </div>
                  <div className="meta-detail-item">
                    <span className="meta-detail-label">Start Date</span>
                    <span className="meta-detail-value">{formatDate(selectedRecord.start_date)}</span>
                  </div>
                  <div className="meta-detail-item">
                    <span className="meta-detail-label">End Date</span>
                    <span className="meta-detail-value">{formatDate(selectedRecord.end_date)}</span>
                  </div>
                </div>
              </div>

              {/* Parser audit logs */}
              {selectedRecord.rejection_reason && (
                <div style={{ padding: '1rem', border: '1px solid rgba(245, 158, 11, 0.2)', background: 'rgba(245, 158, 11, 0.03)', borderRadius: '8px' }}>
                  <p className="drawer-section-title" style={{ color: 'var(--color-warning)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    <AlertTriangle size={14} /> Validation Comments & Warnings
                  </p>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: 1.5, whiteSpace: 'pre-line' }}>
                    {selectedRecord.rejection_reason}
                  </p>
                </div>
              )}

              {/* Calculation Lineage */}
              <div>
                <p className="drawer-section-title">Calculations & Verification Lineage</p>
                <div style={{ background: 'var(--bg-primary)', padding: '1.25rem', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Ingested Amount</span>
                    <strong>{parseFloat(selectedRecord.raw_quantity).toLocaleString()} {selectedRecord.raw_unit}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Normalized Amount</span>
                    <strong>{parseFloat(selectedRecord.normalized_quantity).toLocaleString()} {selectedRecord.normalized_unit}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Calculation Formula</span>
                    <span style={{ color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                      (Quantity * Factor) / 1000
                    </span>
                  </div>
                  
                  {/* Detailed context math depending on source */}
                  {selectedRecord.category === 'FLIGHT' && selectedRecord.raw_data && (
                    <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', border: '1px solid var(--border-color)' }}>
                      <p style={{ fontWeight: 600, color: 'var(--color-scope2)' }}>Travel Segment Calculation Detail:</p>
                      <p>• Flight Path: <strong>{selectedRecord.raw_data['Flight Origin']} ➔ {selectedRecord.raw_data['Flight Destination']}</strong></p>
                      <p>• Calculated Great Circle Distance: <strong>{parseFloat(selectedRecord.raw_quantity).toLocaleString()} km</strong></p>
                      <p>• Cabin Class: <strong>{selectedRecord.raw_data['Cabin Class'] || 'Economy'}</strong></p>
                      <p>• CO2e Factor: <strong>{selectedRecord.activity_type === 'FLIGHT_SHORT_HAUL' ? '0.151 kg/km (Short-haul)' : '0.185 kg/km (Long-haul)'}</strong></p>
                    </div>
                  )}

                  {selectedRecord.category === 'HOTEL' && selectedRecord.raw_data && (
                    <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', border: '1px solid var(--border-color)' }}>
                      <p style={{ fontWeight: 600, color: 'var(--color-scope2)' }}>Hotel Stay Calculation Detail:</p>
                      <p>• Location Assumed: <strong>{selectedRecord.raw_data['Hotel Country'] || 'HQ Base'}</strong></p>
                      <p>• Room Nights: <strong>{selectedRecord.raw_quantity} nights</strong></p>
                    </div>
                  )}

                  {selectedRecord.category === 'ELECTRICITY' && (
                    <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', border: '1px solid var(--border-color)' }}>
                      <p style={{ fontWeight: 600, color: 'var(--color-scope2)' }}>Prorated Billing Cycle Detail:</p>
                      <p>• Billing Meter: <strong>{selectedRecord.raw_data['Meter Number'] || selectedRecord.raw_data['Meter ID']}</strong></p>
                      <p>• Billing Days: <strong>{(new Date(selectedRecord.end_date).getTime() - new Date(selectedRecord.start_date).getTime()) / (1000*3600*24) + 1} days</strong></p>
                    </div>
                  )}
                </div>
              </div>

              {/* Source Row JSON */}
              <div>
                <p className="drawer-section-title">Source of Truth (Raw Upload Row)</p>
                <pre className="raw-json-block">
                  {JSON.stringify(selectedRecord.raw_data, null, 2)}
                </pre>
              </div>

              {/* Historical Audit Trail */}
              <div>
                <p className="drawer-section-title">Immutable Audit Trail Logs</p>
                <div className="audit-timeline">
                  {auditLogs.length === 0 ? (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>No historical edits recorded.</span>
                  ) : (
                    auditLogs.map((log) => (
                      <div className={`timeline-event ${log.action.toLowerCase()}`} key={log.id}>
                        <div className="timeline-event-header">
                          <span className="timeline-event-user">{log.changed_by_username || 'System'}</span>
                          <span className="timeline-event-time">{new Date(log.changed_at).toLocaleString()}</span>
                        </div>
                        <span className="timeline-event-content">
                          Action: <strong>{log.action}</strong> 
                          {log.field_name && (
                            <span> on field <code>{log.field_name}</code></span>
                          )}
                        </span>
                        {log.old_value && (
                          <div className="timeline-change-diff">
                            {log.old_value} ➔ {log.new_value}
                          </div>
                        )}
                        {!log.old_value && log.new_value && (
                          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>{log.new_value}</p>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Drawer Actions */}
          {selectedRecord && (
            <div className="drawer-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                {currentUserProfile?.role === 'ANALYST' && selectedRecord.status !== 'APPROVED' && (
                  <>
                    <button className="btn btn-primary" onClick={() => openEditModal(selectedRecord)}>
                      <Edit3 size={14} /> Edit Row Details
                    </button>
                    <button className="btn btn-success" onClick={() => handleSingleReview('approve', selectedRecord.id)}>
                      <CheckCircle size={14} /> Sign Off
                    </button>
                    <button className="btn btn-danger" onClick={() => handleSingleReview('reject', selectedRecord.id)}>
                      <XCircle size={14} /> Reject
                    </button>
                  </>
                )}
                {selectedRecord.status === 'APPROVED' && (
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600 }}>
                    <CheckCircle size={16} color="var(--color-success)" /> Locked for Audit by {selectedRecord.reviewed_by_username} on {selectedRecord.reviewed_at ? new Date(selectedRecord.reviewed_at).toLocaleDateString() : ''}
                  </div>
                )}
              </div>
              <button className="btn btn-secondary" onClick={() => handleExportAuditTrail(selectedRecord)} style={{ marginLeft: 'auto' }}>
                Export Audit Trail
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Edit Record Modal */}
      <div className={`modal-overlay ${isEditModalOpen ? 'open' : ''}`}>
        <div className="modal-card">
          <div className="modal-header">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Edit Normalized Record</h3>
            <button className="drawer-close" onClick={() => setIsEditModalOpen(false)}>
              <X size={18} />
            </button>
          </div>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Raw Quantity</label>
              <input
                type="text"
                className="form-input"
                value={editQty}
                onChange={(e) => setEditQty(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Activity Type</label>
              <input
                type="text"
                className="form-input"
                value={editActivity}
                onChange={(e) => setEditActivity(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Mapped Facility</label>
              <select
                className="form-input"
                value={editFacility}
                onChange={(e) => setEditFacility(e.target.value)}
              >
                <option value="">No Facility Mapping (Scope 3/Global)</option>
                {facilities.map(f => (
                  <option key={f.id} value={f.id}>{f.name} ({f.plant_code})</option>
                ))}
              </select>
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" onClick={() => setIsEditModalOpen(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={saveRecordEdit}>Recalculate & Save</button>
          </div>
        </div>
      </div>

      {/* Rejection Reason Modal */}
      <div className={`modal-overlay ${isRejectModalOpen ? 'open' : ''}`}>
        <div className="modal-card">
          <div className="modal-header">
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Reject Normalized Records</h3>
            <button className="drawer-close" onClick={() => setIsRejectModalOpen(false)}>
              <X size={18} />
            </button>
          </div>
          <div className="modal-body">
            <div className="form-group">
              <label className="form-label">Rejection Reason / Auditor Notes</label>
              <textarea
                className="form-textarea"
                rows={4}
                placeholder="Explain why this row is being rejected (e.g. meter mismatch, double entry, suspicious spike)..."
                value={rejectionReasonInput}
                onChange={(e) => setRejectionReasonInput(e.target.value)}
              />
            </div>
          </div>
          <div className="modal-footer">
            <button className="btn btn-secondary" onClick={() => { setIsRejectModalOpen(false); setRejectionReasonInput(''); }}>Cancel</button>
            <button className="btn btn-danger" onClick={submitRejection}>Submit Rejection</button>
          </div>
        </div>
      </div>
    </div>
  );
}
