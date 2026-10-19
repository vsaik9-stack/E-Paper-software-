"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  DollarSign,
  Eye,
  FileUp,
  Layers,
  Palette,
  Plus,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useTenant } from "@/components/TenantProvider";

export default function TenantAdminDashboardPage() {
  const { tenant, allTenants, activeTenantSlug, singleTenantMode, switchTenant, refreshTenantConfig } =
    useTenant();

  const [token, setToken] = useState<string>("");
  const [loginEmail, setLoginEmail] = useState<string>("superadmin@platform.com");
  const [loginPassword, setLoginPassword] = useState<string>("Admin@123");
  const [authError, setAuthError] = useState<string>("");

  const [dashboard, setDashboard] = useState<any>(null);
  const [editions, setEditions] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<
    "overview" | "upload" | "editions" | "branding"
  >("overview");

  // Upload Issue Form State
  const [uploadEditionId, setUploadEditionId] = useState<string>("");
  const [uploadDate, setUploadDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string>("");

  // New Edition Form State
  const [newEditionName, setNewEditionName] = useState<string>("");
  const [newEditionSlug, setNewEditionSlug] = useState<string>("");

  // Branding & Monetization Form State
  const [brandName, setBrandName] = useState<string>("");
  const [primaryColor, setPrimaryColor] = useState<string>("#dc2626");
  const [secondaryColor, setSecondaryColor] = useState<string>("#0f172a");
  const [headerTitle, setHeaderTitle] = useState<string>("");
  const [footerText, setFooterText] = useState<string>("");
  const [copyrightText, setCopyrightText] = useState<string>("");
  const [adsenseId, setAdsenseId] = useState<string>("");
  const [autoAds, setAutoAds] = useState<boolean>(false);
  const [headerAdSlot, setHeaderAdSlot] = useState<string>("");
  const [sidebarAdSlot, setSidebarAdSlot] = useState<string>("");
  const [savingBranding, setSavingBranding] = useState<boolean>(false);
  const [brandingSavedMsg, setBrandingSavedMsg] = useState<string>("");

  // Auto-authenticate with demo Super-Admin / Tenant Admin credentials for frictionless testing
  useEffect(() => {
    const saved = localStorage.getItem("epaper_jwt_token");
    if (saved) {
      setToken(saved);
    } else {
      handleLogin("superadmin@platform.com", "Admin@123");
    }
  }, []);

  const handleLogin = async (emailOverride?: string, passOverride?: string) => {
    setAuthError("");
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: emailOverride || loginEmail,
          password: passOverride || loginPassword,
        }),
      });
      if (!res.ok) {
        setAuthError("Invalid credentials. Try superadmin@platform.com / Admin@123");
        return;
      }
      const data = await res.json();
      localStorage.setItem("epaper_jwt_token", data.access_token);
      setToken(data.access_token);
    } catch {
      setAuthError("Failed to connect to authentication server.");
    }
  };

  const loadDashboardAndEditions = async () => {
    if (!token || !tenant) return;
    const headers = {
      Authorization: `Bearer ${token}`,
      "x-tenant-slug": tenant.slug,
    };
    const [dashRes, edRes] = await Promise.all([
      fetch("/api/v1/admin/dashboard", { headers }),
      fetch("/api/v1/admin/editions", { headers }),
    ]);

    if (dashRes.ok) {
      const d = await dashRes.json();
      setDashboard(d);
    }
    if (edRes.ok) {
      const eds = await edRes.json();
      setEditions(eds);
      if (eds.length > 0 && !uploadEditionId) {
        setUploadEditionId(eds[0].id);
      }
    }
  };

  useEffect(() => {
    if (tenant) {
      setBrandName(tenant.name || "");
      setPrimaryColor(tenant.brand_primary_color || "#dc2626");
      setSecondaryColor(tenant.brand_secondary_color || "#0f172a");
      setHeaderTitle(tenant.header_title || "");
      setFooterText(tenant.footer_text || "");
      setCopyrightText(tenant.copyright_text || "");
      setAdsenseId(tenant.monetization_settings?.adsense_client_id || "");
      setAutoAds(Boolean(tenant.monetization_settings?.auto_ads));
      setHeaderAdSlot(tenant.monetization_settings?.header_ad_slot || "");
      setSidebarAdSlot(tenant.monetization_settings?.sidebar_ad_slot || "");
    }
    if (token && tenant) {
      loadDashboardAndEditions();
    }
  }, [token, tenant?.slug]);

  const handleUploadPdf = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile || !uploadEditionId || !tenant) return;
    setUploading(true);
    setUploadSuccess("");

    try {
      const formData = new FormData();
      formData.append("edition_id", uploadEditionId);
      formData.append("publication_date", uploadDate);
      formData.append("sync_process", "true");
      formData.append("file", selectedFile);

      const res = await fetch("/api/v1/admin/issues/upload", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "x-tenant-slug": tenant.slug,
        },
        body: formData,
      });

      if (res.ok) {
        const result = await res.json();
        setUploadSuccess(
          `Successfully processed & published ${result.page_count} pages into 512x512 WebP DeepZoom pyramid tiles!`
        );
        setSelectedFile(null);
        await loadDashboardAndEditions();
      } else {
        const err = await res.json();
        alert(`Upload error: ${err.detail || "Failed"}`);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleCreateEdition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEditionName || !tenant) return;

    const res = await fetch("/api/v1/admin/editions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "x-tenant-slug": tenant.slug,
      },
      body: JSON.stringify({
        name: newEditionName,
        slug:
          newEditionSlug ||
          newEditionName.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        display_order: editions.length + 1,
        is_active: true,
      }),
    });

    if (res.ok) {
      setNewEditionName("");
      setNewEditionSlug("");
      await loadDashboardAndEditions();
      await refreshTenantConfig();
    }
  };

  const handleDeleteIssue = async (issueId: string) => {
    if (!tenant) return;
    await fetch(`/api/v1/admin/issues/${issueId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        "x-tenant-slug": tenant.slug,
      },
    });
    await loadDashboardAndEditions();
  };

  const handleSaveBranding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenant) return;
    setSavingBranding(true);
    setBrandingSavedMsg("");

    try {
      const res = await fetch("/api/v1/admin/branding", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "x-tenant-slug": tenant.slug,
        },
        body: JSON.stringify({
          name: brandName,
          brand_primary_color: primaryColor,
          brand_secondary_color: secondaryColor,
          header_title: headerTitle,
          footer_text: footerText,
          copyright_text: copyrightText,
          monetization_settings: {
            adsense_client_id: adsenseId,
            auto_ads: autoAds,
            header_ad_slot: headerAdSlot,
            sidebar_ad_slot: sidebarAdSlot,
          },
        }),
      });
      if (res.ok) {
        await refreshTenantConfig();
        await loadDashboardAndEditions();
        setBrandingSavedMsg(
          "White-Label Branding & AdSense Monetization settings updated live!"
        );
      }
    } finally {
      setSavingBranding(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Bar */}
      <header
        className="bg-slate-900 text-white px-6 py-4 flex flex-wrap items-center justify-between gap-4 border-b border-slate-800"
        style={{ borderTop: `4px solid var(--primary-color, #dc2626)` }}
      >
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center gap-1.5 text-xs font-bold transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Reader</span>
          </Link>
          <div>
            <h1 className="text-lg font-black tracking-tight flex items-center gap-2">
              <span>{tenant?.name} • Publisher Admin Portal</span>
              <span
                className="text-[10px] px-2 py-0.5 rounded-full uppercase font-extrabold"
                style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
              >
                {tenant?.slug}
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Multi-Tenant Scoped CMS • Manage Editions, Upload 300-DPI PDFs & Customize Branding
            </p>
          </div>
        </div>

        {/* Switch Tenant inside Admin (Hidden in Single-Tenant Client Mode) */}
        {!singleTenantMode && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Active Tenant:</span>
            {allTenants.map((t) => (
              <button
                key={t.id}
                onClick={() => switchTenant(t.slug)}
                className={`px-3 py-1 rounded-lg text-xs font-bold transition cursor-pointer ${
                  t.slug === activeTenantSlug
                    ? "text-white shadow"
                    : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                }`}
                style={
                  t.slug === activeTenantSlug
                    ? { backgroundColor: t.brand_primary_color }
                    : undefined
                }
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
      </header>

      <div className="max-w-7xl w-full mx-auto p-6 flex-1 flex flex-col gap-6">
        {/* Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 pb-3">
          {[
            { id: "overview", label: "Dashboard & Issues", icon: Eye },
            { id: "upload", label: "Upload Newspaper PDF", icon: FileUp },
            { id: "editions", label: "Regional Editions", icon: Layers },
            {
              id: "branding",
              label: "White-Label Branding & AdSense",
              icon: Palette,
            },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold flex items-center gap-2 transition cursor-pointer ${
                  active
                    ? "text-white shadow-sm"
                    : "bg-white text-slate-700 hover:bg-slate-100 border border-slate-200"
                }`}
                style={
                  active
                    ? { backgroundColor: "var(--primary-color, #dc2626)" }
                    : undefined
                }
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* TAB 1: OVERVIEW & ISSUES */}
        {activeTab === "overview" && (
          <div className="flex flex-col gap-6">
            {/* Metric Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
                <span className="text-xs font-bold uppercase text-slate-400">
                  Total Page Views
                </span>
                <p className="text-3xl font-black text-slate-900 mt-1">
                  {dashboard?.metrics?.total_views || 0}
                </p>
                <span className="text-[11px] text-emerald-600 font-semibold">
                  +18% vs yesterday
                </span>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
                <span className="text-xs font-bold uppercase text-slate-400">
                  Published Issues
                </span>
                <p className="text-3xl font-black text-slate-900 mt-1">
                  {dashboard?.metrics?.issues_count || 0}
                </p>
                <span className="text-[11px] text-slate-500">
                  Scoped to {tenant?.name}
                </span>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
                <span className="text-xs font-bold uppercase text-slate-400">
                  Regional Editions
                </span>
                <p className="text-3xl font-black text-slate-900 mt-1">
                  {dashboard?.metrics?.editions_count || 0}
                </p>
                <span className="text-[11px] text-slate-500">
                  Active Editions
                </span>
              </div>

              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-2xs">
                <span className="text-xs font-bold uppercase text-slate-400">
                  DeepZoom Pages Rendered
                </span>
                <p className="text-3xl font-black text-slate-900 mt-1">
                  {dashboard?.metrics?.total_pages_rendered || 0}
                </p>
                <span className="text-[11px] text-indigo-600 font-semibold">
                  512x512 WebP Tile Pyramids
                </span>
              </div>
            </div>

            {/* Issues Table */}
            <div className="bg-white rounded-2xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                <h2 className="font-extrabold text-slate-900">
                  Recent Published Issues ({tenant?.name})
                </h2>
                <button
                  onClick={() => setActiveTab("upload")}
                  className="px-3.5 py-2 rounded-xl text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer"
                  style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
                >
                  <Plus className="w-4 h-4" />
                  <span>Upload New Issue PDF</span>
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-slate-500 text-xs uppercase">
                      <th className="py-3 px-6">Publication Date</th>
                      <th className="py-3 px-4">Edition</th>
                      <th className="py-3 px-4">Pages</th>
                      <th className="py-3 px-4">Status & DeepZoom Progress</th>
                      <th className="py-3 px-4">Views</th>
                      <th className="py-3 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {dashboard?.recent_issues?.map((iss: any) => (
                      <tr key={iss.id} className="hover:bg-slate-50">
                        <td className="py-3.5 px-6 font-bold text-slate-900">
                          {iss.publication_date}{" "}
                          <span className="text-xs text-slate-400 font-normal">
                            (Rev {iss.revision})
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-700">
                          {iss.edition_name}
                        </td>
                        <td className="py-3.5 px-4">{iss.page_count} Pages</td>
                        <td className="py-3.5 px-4">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>{iss.status}</span>
                          </span>
                        </td>
                        <td className="py-3.5 px-4 font-semibold">
                          {iss.views_count}
                        </td>
                        <td className="py-3.5 px-6 text-right">
                          <button
                            onClick={() => handleDeleteIssue(iss.id)}
                            className="p-1.5 text-rose-600 hover:bg-rose-50 rounded-lg transition cursor-pointer"
                            title="Delete Issue"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PDF UPLOADER */}
        {activeTab === "upload" && (
          <div className="bg-white rounded-2xl border border-slate-200 p-6 max-w-2xl shadow-2xs">
            <h2 className="text-lg font-black text-slate-900 mb-1">
              Upload Multi-Page Newspaper PDF
            </h2>
            <p className="text-xs text-slate-500 mb-6">
              Our PyMuPDF engine validates vector integrity, normalizes CMYK to sRGB, and generates 300-DPI WebP images + 512x512 DeepZoom DZI tile pyramids automatically.
            </p>

            {uploadSuccess && (
              <div className="mb-5 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold flex items-center justify-between">
                <span>{uploadSuccess}</span>
                <Link
                  href="/"
                  className="px-3 py-1.5 rounded-lg bg-emerald-700 text-white"
                >
                  View in Reader →
                </Link>
              </div>
            )}

            <form onSubmit={handleUploadPdf} className="flex flex-col gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Target Edition
                </label>
                <select
                  value={uploadEditionId}
                  onChange={(e) => setUploadEditionId(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm font-semibold"
                  required
                >
                  {editions.map((ed) => (
                    <option key={ed.id} value={ed.id}>
                      {ed.name} ({ed.slug})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Publication Date
                </label>
                <input
                  type="date"
                  value={uploadDate}
                  onChange={(e) => setUploadDate(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm font-semibold"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Broadsheet PDF File
                </label>
                <input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) =>
                    setSelectedFile(e.target.files?.[0] || null)
                  }
                  className="w-full border-2 border-dashed border-slate-300 rounded-xl p-6 text-sm cursor-pointer bg-slate-50 hover:bg-slate-100 transition"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={uploading || !selectedFile}
                className="mt-2 py-3 px-5 rounded-xl text-white font-extrabold text-sm shadow flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
                style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
              >
                <FileUp className="w-4 h-4" />
                <span>
                  {uploading
                    ? "Rendering 300-DPI DeepZoom Pyramid Tiles..."
                    : "Upload & Publish Issue Live"}
                </span>
              </button>
            </form>
          </div>
        )}

        {/* TAB 3: EDITIONS MANAGEMENT */}
        {activeTab === "editions" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs">
              <h3 className="text-base font-black text-slate-900 mb-4">
                Active Editions for {tenant?.name}
              </h3>
              <div className="flex flex-col gap-2.5">
                {editions.map((ed) => (
                  <div
                    key={ed.id}
                    className="p-3.5 rounded-xl border border-slate-200 flex items-center justify-between bg-slate-50"
                  >
                    <div>
                      <p className="font-bold text-sm text-slate-900">
                        {ed.name}
                      </p>
                      <p className="text-xs text-slate-500">
                        Slug: <code>{ed.slug}</code> • Order #{ed.display_order}
                      </p>
                    </div>
                    <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                      Active
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs">
              <h3 className="text-base font-black text-slate-900 mb-4">
                Create New Regional Edition
              </h3>
              <form
                onSubmit={handleCreateEdition}
                className="flex flex-col gap-4"
              >
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Edition Name (e.g. Tirupati Main, Nizamabad)
                  </label>
                  <input
                    type="text"
                    value={newEditionName}
                    onChange={(e) => setNewEditionName(e.target.value)}
                    placeholder="e.g. Karimnagar District"
                    className="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Edition URL Slug
                  </label>
                  <input
                    type="text"
                    value={newEditionSlug}
                    onChange={(e) => setNewEditionSlug(e.target.value)}
                    placeholder="e.g. karimnagar"
                    className="w-full border border-slate-300 rounded-xl px-3.5 py-2.5 text-sm"
                  />
                </div>
                <button
                  type="submit"
                  className="py-2.5 px-4 rounded-xl text-white font-bold text-sm cursor-pointer"
                  style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
                >
                  + Add Regional Edition
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TAB 4: WHITE-LABEL BRANDING & MONETIZATION */}
        {activeTab === "branding" && (
          <form
            onSubmit={handleSaveBranding}
            className="bg-white rounded-2xl border border-slate-200 p-6 shadow-2xs max-w-3xl flex flex-col gap-5"
          >
            <div>
              <h2 className="text-lg font-black text-slate-900">
                White-Label Theme & Google AdSense Monetization
              </h2>
              <p className="text-xs text-slate-500">
                Changes made here update CSS variables (<code>--primary-color</code>), masthead titles, clipping watermarks, and AdSense slots in real time.
              </p>
            </div>

            {brandingSavedMsg && (
              <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-bold">
                {brandingSavedMsg}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Newspaper Publication Name
                </label>
                <input
                  type="text"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-3.5 py-2 text-sm font-semibold"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Header Browser Title
                </label>
                <input
                  type="text"
                  value={headerTitle}
                  onChange={(e) => setHeaderTitle(e.target.value)}
                  className="w-full border border-slate-300 rounded-xl px-3.5 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Brand Primary Color (Hex)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="h-10 w-14 rounded border border-slate-300 cursor-pointer"
                  />
                  <input
                    type="text"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="flex-1 border border-slate-300 rounded-xl px-3.5 py-2 text-sm font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                  Brand Secondary Color (Hex)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="h-10 w-14 rounded border border-slate-300 cursor-pointer"
                  />
                  <input
                    type="text"
                    value={secondaryColor}
                    onChange={(e) => setSecondaryColor(e.target.value)}
                    className="flex-1 border border-slate-300 rounded-xl px-3.5 py-2 text-sm font-mono"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                Clipping Watermark & Copyright Footer Text
              </label>
              <input
                type="text"
                value={copyrightText}
                onChange={(e) => setCopyrightText(e.target.value)}
                className="w-full border border-slate-300 rounded-xl px-3.5 py-2 text-sm"
              />
            </div>

            <div className="pt-4 border-t border-slate-200">
              <h3 className="text-sm font-black text-slate-900 flex items-center gap-1.5 mb-3">
                <DollarSign className="w-4 h-4 text-emerald-600" />
                <span>Monetization & AdSense Slots</span>
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    AdSense Publisher ID
                  </label>
                  <input
                    type="text"
                    value={adsenseId}
                    onChange={(e) => setAdsenseId(e.target.value)}
                    placeholder="ca-pub-xxxxxxxxxxxxxxxx"
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Header Banner Slot ID
                  </label>
                  <input
                    type="text"
                    value={headerAdSlot}
                    onChange={(e) => setHeaderAdSlot(e.target.value)}
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase text-slate-600 mb-1">
                    Sidebar Ad Slot ID
                  </label>
                  <input
                    type="text"
                    value={sidebarAdSlot}
                    onChange={(e) => setSidebarAdSlot(e.target.value)}
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 text-sm"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={savingBranding}
              className="py-3 px-6 rounded-xl text-white font-extrabold text-sm self-start cursor-pointer shadow"
              style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
            >
              {savingBranding
                ? "Saving Configuration..."
                : "Save Branding & Monetization Settings"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
