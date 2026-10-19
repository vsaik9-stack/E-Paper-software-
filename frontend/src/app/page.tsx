"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Globe,
  Grid,
  Layers,
  Maximize2,
  Newspaper,
  Scissors,
  Share2,
  ShieldCheck,
  Sparkles,
  Volume2,
  VolumeX,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { useTenant } from "@/components/TenantProvider";
import { CropBox, CropOverlay } from "@/components/reader/CropOverlay";
import type { RenderedPageBounds } from "@/components/reader/OSDViewer";
import { playPaperTurnSound } from "@/lib/sound";

const OSDViewer = dynamic(
  () => import("@/components/reader/OSDViewer").then((mod) => mod.OSDViewer),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex flex-col items-center justify-center bg-slate-900 text-slate-300 gap-3">
        <div className="w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-semibold tracking-wider uppercase">
          Initializing 512x512 WebP DeepZoom Pyramid Engine...
        </p>
      </div>
    ),
  }
);

interface ArticleRegionItem {
  id: string;
  page_id: string;
  title: string;
  coordinates: { x: number; y: number; width: number; height: number };
  content_text?: string | null;
  clip_url?: string | null;
}

interface PageItem {
  id: string;
  page_number: number;
  title?: string;
  width: number;
  height: number;
  dpi: number;
  large_url?: string;
  medium_url?: string;
  thumbnail_url?: string;
  dzi_url?: string;
  articles: ArticleRegionItem[];
}

interface IssueData {
  id: string;
  tenant_id: string;
  edition_id: string;
  edition_name: string;
  edition_slug: string;
  publication_date: string;
  revision: number;
  page_count: number;
  status: string;
  pdf_url?: string;
  pages: PageItem[];
}

interface ArchiveItem {
  publication_date: string;
  issue_id: string;
  edition_slug: string;
  edition_name: string;
  page_count: number;
  thumbnail_url?: string;
}

interface ClipResult {
  clip_id: string;
  clip_url: string;
  share_text: string;
  tenant_name: string;
  edition_name: string;
  publication_date: string;
  page_number: number;
}

export default function WhiteLabelReaderPage() {
  const { tenant, allTenants, activeTenantSlug, singleTenantMode, switchTenant } = useTenant();

  const [selectedEdition, setSelectedEdition] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [issue, setIssue] = useState<IssueData | null>(null);
  const [archiveDates, setArchiveDates] = useState<ArchiveItem[]>([]);
  const [currentPageIdx, setCurrentPageIdx] = useState<number>(0);
  const [zoomLevel, setZoomLevel] = useState<number>(1.0);
  const [soundEnabled, setSoundEnabled] = useState<boolean>(true);
  const [isCropMode, setIsCropMode] = useState<boolean>(false);
  const [pageBounds, setPageBounds] = useState<RenderedPageBounds | null>(null);
  const [loadingIssue, setLoadingIssue] = useState<boolean>(true);

  // Modals & Drawers
  const [showMobileThumbs, setShowMobileThumbs] = useState<boolean>(false);
  const [showArchiveModal, setShowArchiveModal] = useState<boolean>(false);
  const [activeArticleModal, setActiveArticleModal] =
    useState<ArticleRegionItem | null>(null);
  const [clippingLoading, setClippingLoading] = useState<boolean>(false);
  const [clipResult, setClipResult] = useState<ClipResult | null>(null);

  // Sync default edition when tenant changes
  useEffect(() => {
    if (tenant && tenant.editions && tenant.editions.length > 0) {
      setSelectedEdition(tenant.editions[0].slug);
      setSelectedDate("");
    }
  }, [tenant?.id]);

  // Fetch issue & archive whenever tenant, edition, or date changes
  useEffect(() => {
    if (!tenant) return;

    const loadIssueAndArchive = async () => {
      setLoadingIssue(true);
      try {
        const headers: Record<string, string> = {
          "x-tenant-slug": tenant.slug,
        };
        const params = new URLSearchParams();
        if (selectedEdition) params.set("edition", selectedEdition);
        if (selectedDate) params.set("pub_date", selectedDate);

        const [issueRes, archRes] = await Promise.all([
          fetch(`/api/v1/reader/today?${params.toString()}`, {
            headers,
            cache: "no-store",
          }),
          fetch(
            `/api/v1/reader/archive${
              selectedEdition ? `?edition=${selectedEdition}` : ""
            }`,
            { headers, cache: "no-store" }
          ),
        ]);

        if (issueRes.ok) {
          const data: IssueData = await issueRes.json();
          setIssue(data);
          setCurrentPageIdx(0);
          setZoomLevel(1.0);
          setIsCropMode(false);
        } else {
          setIssue(null);
        }

        if (archRes.ok) {
          const archData: ArchiveItem[] = await archRes.json();
          setArchiveDates(archData);
        }
      } catch (err) {
        console.error("Error loading reader issue:", err);
      } finally {
        setLoadingIssue(false);
      }
    };

    loadIssueAndArchive();
  }, [tenant?.slug, selectedEdition, selectedDate]);

  const currentPage: PageItem | null =
    issue && issue.pages && issue.pages[currentPageIdx]
      ? issue.pages[currentPageIdx]
      : null;

  const goToPage = (index: number) => {
    if (!issue || index < 0 || index >= issue.pages.length) return;
    if (index !== currentPageIdx && soundEnabled) {
      playPaperTurnSound();
    }
    setIsCropMode(false);
    setZoomLevel(1.0);
    setCurrentPageIdx(index);
  };

  // Keyboard navigation (Left/Right arrows)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isCropMode || activeArticleModal || clipResult) return;
      if (e.key === "ArrowRight") {
        goToPage(currentPageIdx + 1);
      } else if (e.key === "ArrowLeft") {
        goToPage(currentPageIdx - 1);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentPageIdx, issue, isCropMode, activeArticleModal, clipResult, soundEnabled]);

  const handleCropComplete = async (box: CropBox) => {
    if (!issue || !currentPage || !tenant) return;
    setClippingLoading(true);
    try {
      const res = await fetch("/api/v1/clipping/crop", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-tenant-slug": tenant.slug,
        },
        body: JSON.stringify({
          issue_id: issue.id,
          page_number: currentPage.page_number,
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
        }),
      });
      if (res.ok) {
        const result: ClipResult = await res.json();
        setClipResult(result);
        setIsCropMode(false);
      }
    } catch (e) {
      console.error("Failed to generate clip:", e);
    } finally {
      setClippingLoading(false);
    }
  };

  // Map backend ArticleRegion items to OSDViewer format
  const mappedArticles =
    currentPage?.articles?.map((art) => ({
      id: art.id,
      headline: art.title,
      content_text: art.content_text,
      bounds: art.coordinates,
      raw: art,
    })) || [];

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-900 select-none">
      {/* 1. SaaS Multi-Tenant Live Switcher & Domain Resolver Status Bar (Hidden in Single-Tenant Client Mode) */}
      {!singleTenantMode && (
        <div className="bg-slate-950 text-slate-300 border-b border-slate-800 px-3 py-1.5 flex items-center justify-between text-xs z-40 shrink-0">
          <div className="flex items-center gap-2 overflow-x-auto">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 font-semibold border border-emerald-500/30">
              <Globe className="w-3 h-3" />
              <span>Multi-Tenant Domain Resolver</span>
            </span>
            <span className="text-slate-400 hidden sm:inline">Switch Newspaper Client:</span>
            <div className="flex items-center gap-1">
              {allTenants.map((t) => {
                const isActive = t.slug === activeTenantSlug;
                return (
                  <button
                    key={t.id}
                    onClick={() => switchTenant(t.slug)}
                    className={`px-2.5 py-0.5 rounded-md font-bold transition flex items-center gap-1.5 cursor-pointer ${
                      isActive
                        ? "text-white shadow-sm"
                        : "bg-slate-800/80 text-slate-300 hover:bg-slate-800"
                    }`}
                    style={
                      isActive
                        ? { backgroundColor: t.brand_primary_color }
                        : undefined
                    }
                  >
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{
                        backgroundColor: isActive ? "#fff" : t.brand_primary_color,
                      }}
                    />
                    <span>{t.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Link
              href="/admin"
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold flex items-center gap-1 transition"
            >
              <Layers className="w-3.5 h-3.5 text-amber-400" />
              <span>Client Uploader (/admin)</span>
            </Link>
            <Link
              href="/superadmin"
              className="px-2.5 py-1 rounded bg-indigo-600/90 hover:bg-indigo-600 text-white font-semibold flex items-center gap-1 transition"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">VPS & Client Fleet Manager</span>
            </Link>
          </div>
        </div>
      )}

      {/* 2. White-Label Newspaper Masthead & Desktop Top Control Dock */}
      <header
        className="bg-white border-b border-slate-200 px-3 sm:px-5 py-2.5 flex items-center justify-between shadow-sm z-30 shrink-0"
        style={{
          borderTop: `4px solid var(--primary-color, #dc2626)`,
        }}
      >
        {/* Left: Tenant Brand Logo / Masthead & Edition Switcher */}
        <div className="flex items-center gap-3 sm:gap-5">
          <div className="flex items-center gap-2.5">
            {tenant?.logo_url ? (
              <img
                src={tenant.logo_url}
                alt={tenant.name}
                className="h-9 sm:h-11 object-contain"
              />
            ) : (
              <div className="flex items-center gap-2.5">
                <div
                  className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center text-white font-black text-lg shadow-sm"
                  style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
                >
                  {tenant?.name?.charAt(0) || "E"}
                </div>
                <div>
                  <h1
                    className="font-black text-lg sm:text-2xl tracking-tight leading-none uppercase"
                    style={{ color: "var(--primary-color, #dc2626)" }}
                  >
                    {tenant?.name || "Loading..."}
                  </h1>
                  <p className="text-[10px] sm:text-xs font-bold text-slate-500 tracking-wider uppercase mt-0.5">
                    {issue?.edition_name || "Digital Broadsheet Edition"} •{" "}
                    {issue?.publication_date || ""}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Edition Selector Dropdown */}
          {tenant?.editions && tenant.editions.length > 0 && (
            <div className="hidden md:flex items-center gap-1.5 bg-slate-100 px-2.5 py-1.5 rounded-lg border border-slate-200">
              <Newspaper className="w-4 h-4 text-slate-500" />
              <select
                value={selectedEdition}
                onChange={(e) => setSelectedEdition(e.target.value)}
                className="bg-transparent text-xs font-bold text-slate-800 focus:outline-none cursor-pointer"
              >
                {tenant.editions.map((ed) => (
                  <option key={ed.id} value={ed.slug}>
                    {ed.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Archive Calendar Picker Button */}
          <button
            onClick={() => setShowArchiveModal(true)}
            className="hidden sm:flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-bold transition cursor-pointer"
          >
            <Calendar className="w-4 h-4 text-brand-primary" />
            <span>{issue?.publication_date || "Archive"}</span>
          </button>
        </div>

        {/* Center: Desktop Page Turn Controls & Quick Page Jumper */}
        <div className="hidden lg:flex items-center gap-1.5 bg-slate-900 text-white px-2.5 py-1.5 rounded-xl shadow-inner">
          <button
            onClick={() => goToPage(currentPageIdx - 1)}
            disabled={!issue || currentPageIdx <= 0}
            className="p-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-35 transition cursor-pointer"
            title="Previous Page (Left Arrow)"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-1 px-2">
            {issue?.pages?.map((p, idx) => {
              const active = idx === currentPageIdx;
              return (
                <button
                  key={p.id}
                  onClick={() => goToPage(idx)}
                  className={`w-7 h-7 rounded-lg text-xs font-extrabold transition cursor-pointer ${
                    active
                      ? "text-white shadow"
                      : "text-slate-300 hover:bg-slate-800"
                  }`}
                  style={
                    active
                      ? { backgroundColor: "var(--primary-color, #dc2626)" }
                      : undefined
                  }
                >
                  {p.page_number}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => goToPage(currentPageIdx + 1)}
            disabled={!issue || currentPageIdx >= (issue?.pages?.length || 1) - 1}
            className="p-1.5 rounded-lg hover:bg-slate-800 disabled:opacity-35 transition cursor-pointer"
            title="Next Page (Right Arrow)"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Right: Desktop Zoom, Audio Toggle, Clip Tool, and Full PDF Download */}
        <div className="flex items-center gap-2">
          {/* Zoom Controls */}
          <div className="hidden md:flex items-center bg-slate-100 rounded-lg p-0.5 border border-slate-200">
            <button
              onClick={() => setZoomLevel((z) => Math.max(1, Number((z - 0.4).toFixed(1))))}
              className="p-1.5 text-slate-700 hover:bg-white rounded-md transition cursor-pointer"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={() => setZoomLevel(1.0)}
              className="px-2 text-xs font-bold text-slate-700 hover:text-slate-900 cursor-pointer"
              title="Reset Zoom"
            >
              {Math.round(zoomLevel * 100)}%
            </button>
            <button
              onClick={() => setZoomLevel((z) => Math.min(4, Number((z + 0.4).toFixed(1))))}
              className="p-1.5 text-slate-700 hover:bg-white rounded-md transition cursor-pointer"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          {/* Paper Turn Sound Toggle */}
          <button
            onClick={() => {
              const nextState = !soundEnabled;
              setSoundEnabled(nextState);
              if (nextState) playPaperTurnSound();
            }}
            className={`p-2 rounded-lg border text-xs font-bold transition cursor-pointer flex items-center gap-1 ${
              soundEnabled
                ? "bg-amber-50 border-amber-200 text-amber-800"
                : "bg-slate-100 border-slate-200 text-slate-500"
            }`}
            title="Toggle Realistic Broadsheet Page-Turn Sound"
          >
            {soundEnabled ? (
              <Volume2 className="w-4 h-4 text-amber-600" />
            ) : (
              <VolumeX className="w-4 h-4" />
            )}
            <span className="hidden xl:inline">Paper Sound</span>
          </button>

          {/* 8-Point ब्रांडेड Clip & Share Button */}
          <button
            onClick={() => setIsCropMode((prev) => !prev)}
            className={`px-3 py-2 rounded-lg font-bold text-xs sm:text-sm flex items-center gap-1.5 shadow-sm transition cursor-pointer ${
              isCropMode
                ? "bg-slate-900 text-white ring-2 ring-sky-400"
                : "text-white hover:opacity-95"
            }`}
            style={
              !isCropMode
                ? { backgroundColor: "var(--primary-color, #dc2626)" }
                : undefined
            }
          >
            <Scissors className="w-4 h-4" />
            <span>{isCropMode ? "Exit Clip" : "Clip & Share"}</span>
          </button>

          {/* Download Full Issue PDF */}
          {issue?.pdf_url && (
            <a
              href={issue.pdf_url}
              download={`${tenant?.slug || "epaper"}_${issue.publication_date}.pdf`}
              target="_blank"
              rel="noreferrer"
              className="hidden sm:flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white px-3 py-2 rounded-lg text-xs font-bold transition"
              title="Download Full Broadsheet PDF"
            >
              <Download className="w-4 h-4" />
              <span className="hidden xl:inline">PDF</span>
            </a>
          )}
        </div>
      </header>

      {/* 3. Configurable Tenant Header Monetization / Ad Slot */}
      {tenant?.monetization_settings?.header_ad_slot && (
        <div className="bg-slate-100 border-b border-slate-200 py-1 px-4 flex items-center justify-center shrink-0">
          <div className="max-w-4xl w-full bg-white border border-dashed border-slate-300 rounded px-4 py-1 flex items-center justify-between text-[11px] text-slate-500">
            <span className="font-bold uppercase tracking-wider text-slate-400">
              Sponsored • {tenant.name} Ad Network (Slot #{tenant.monetization_settings.header_ad_slot})
            </span>
            <span className="text-slate-600 font-medium hidden sm:inline">
              Advertise across {tenant.name} Digital Editions — Reach 100,000+ Daily Readers
            </span>
            <span
              className="font-bold px-2 py-0.5 rounded text-white text-[10px]"
              style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
            >
              AdSense Ready
            </span>
          </div>
        </div>
      )}

      {/* 4. Main Broadsheet Reader Workspace */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar: High-Speed WebP Page Thumbnails Strip (Desktop) */}
        <aside className="hidden md:flex flex-col w-44 lg:w-52 bg-slate-950 border-r border-slate-800 overflow-y-auto p-3 gap-3 shrink-0">
          <div className="flex items-center justify-between text-xs font-bold text-slate-400 uppercase tracking-wider px-1">
            <span>Pages ({issue?.pages?.length || 0})</span>
            <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
              300 DPI DZI
            </span>
          </div>

          {issue?.pages?.map((p, idx) => {
            const isSelected = idx === currentPageIdx;
            return (
              <button
                key={p.id}
                onClick={() => goToPage(idx)}
                className={`group relative rounded-xl overflow-hidden border-2 transition-all text-left flex flex-col bg-slate-900 cursor-pointer ${
                  isSelected
                    ? "ring-2 ring-offset-2 ring-offset-slate-950 shadow-lg"
                    : "border-slate-800 hover:border-slate-600 opacity-80 hover:opacity-100"
                }`}
                style={
                  isSelected
                    ? {
                        borderColor: "var(--primary-color, #dc2626)",
                      }
                    : undefined
                }
              >
                <div className="aspect-[2/3] w-full bg-slate-800 relative overflow-hidden">
                  {p.thumbnail_url ? (
                    <img
                      src={p.thumbnail_url}
                      alt={`Page ${p.page_number}`}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-200"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-500 text-xs">
                      Page {p.page_number}
                    </div>
                  )}
                </div>
                <div
                  className={`px-2.5 py-1.5 text-xs font-bold flex items-center justify-between ${
                    isSelected ? "text-white" : "bg-slate-900 text-slate-300"
                  }`}
                  style={
                    isSelected
                      ? { backgroundColor: "var(--primary-color, #dc2626)" }
                      : undefined
                  }
                >
                  <span>Page {p.page_number}</span>
                  {p.articles?.length > 0 && (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-black/25">
                      {p.articles.length} stories
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </aside>

        {/* Center Canvas: OpenSeadragon 512x512 WebP DeepZoom Viewer + 8-Point CropOverlay */}
        <main className="flex-1 relative bg-slate-900 overflow-hidden flex items-center justify-center">
          {loadingIssue ? (
            <div className="flex flex-col items-center gap-3 text-slate-300">
              <div className="w-10 h-10 border-4 border-brand-primary border-t-transparent rounded-full animate-spin" />
              <p className="text-sm font-bold">
                Loading {tenant?.name} Digital Broadsheet...
              </p>
            </div>
          ) : !currentPage ? (
            <div className="bg-slate-800/90 border border-slate-700 rounded-2xl p-8 text-center max-w-md mx-4 text-slate-200">
              <Newspaper className="w-12 h-12 mx-auto mb-3 text-slate-400" />
              <h2 className="text-lg font-bold">No Published Issue Found</h2>
              <p className="text-xs text-slate-400 mt-1 mb-4">
                Upload a multi-page newspaper PDF from the Publisher Admin Portal to generate 300-DPI DeepZoom tiles.
              </p>
              <Link
                href="/admin"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-white font-bold text-xs shadow"
                style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
              >
                <span>Open Publisher Admin</span>
              </Link>
            </div>
          ) : (
            <div className="w-full h-full relative">
              <OSDViewer
                imageUrl={currentPage.large_url || ""}
                dziUrl={currentPage.dzi_url}
                mappedArticles={mappedArticles}
                onArticleClick={(art) => setActiveArticleModal(art.raw)}
                zoomLevel={zoomLevel}
                onZoomChange={(z) => setZoomLevel(z)}
                onZoomReset={() => setZoomLevel(1.0)}
                onPageBoundsChange={(bounds) => setPageBounds(bounds)}
                isCropMode={isCropMode}
              />

              {/* 8-Point Resizable Article Crop Tool Overlay */}
              {isCropMode && (
                <CropOverlay
                  pageBounds={pageBounds}
                  onCropComplete={handleCropComplete}
                  onCancel={() => setIsCropMode(false)}
                />
              )}

              {/* Floating Quick Prev / Next Side Paddles on Desktop */}
              {!isCropMode && (
                <>
                  {currentPageIdx > 0 && (
                    <button
                      onClick={() => goToPage(currentPageIdx - 1)}
                      className="hidden sm:flex absolute left-3 top-1/2 -translate-y-1/2 z-20 w-10 h-16 rounded-xl bg-slate-950/75 hover:bg-slate-950 text-white items-center justify-center shadow-xl border border-slate-700/70 transition cursor-pointer"
                      title="Previous Page"
                    >
                      <ChevronLeft className="w-6 h-6" />
                    </button>
                  )}
                  {issue && currentPageIdx < issue.pages.length - 1 && (
                    <button
                      onClick={() => goToPage(currentPageIdx + 1)}
                      className="hidden sm:flex absolute right-3 top-1/2 -translate-y-1/2 z-20 w-10 h-16 rounded-xl bg-slate-950/75 hover:bg-slate-950 text-white items-center justify-center shadow-xl border border-slate-700/70 transition cursor-pointer"
                      title="Next Page"
                    >
                      <ChevronRight className="w-6 h-6" />
                    </button>
                  )}
                </>
              )}

              {/* Clipping Generation Spinner Overlay */}
              {clippingLoading && (
                <div className="absolute inset-0 z-50 bg-slate-950/75 backdrop-blur-xs flex flex-col items-center justify-center text-white gap-3">
                  <div className="w-11 h-11 border-4 border-white border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm font-bold tracking-wide">
                    Compositing High-DPI Crop with {tenant?.name} Masthead Banner...
                  </p>
                </div>
              )}
            </div>
          )}
        </main>

        {/* Right Sidebar: Smart Mapped Articles & Tenant Sidebar Ad Slot (Large Desktop) */}
        <aside className="hidden xl:flex flex-col w-72 bg-white border-l border-slate-200 overflow-y-auto p-4 gap-4 shrink-0">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-brand-primary" />
                <span>Smart Text View (Page {currentPage?.page_number || 1})</span>
              </h3>
            </div>
            {currentPage?.articles && currentPage.articles.length > 0 ? (
              <div className="flex flex-col gap-2.5">
                {currentPage.articles.map((art) => (
                  <button
                    key={art.id}
                    onClick={() => setActiveArticleModal(art)}
                    className="text-left p-3 rounded-xl border border-slate-200 hover:border-slate-400 bg-slate-50/70 hover:bg-white transition shadow-2xs group cursor-pointer"
                  >
                    <h4 className="text-xs font-bold text-slate-900 group-hover:text-brand-primary leading-snug">
                      {art.title}
                    </h4>
                    {art.content_text && (
                      <p className="text-[11px] text-slate-600 line-clamp-2 mt-1">
                        {art.content_text}
                      </p>
                    )}
                    <span
                      className="inline-block mt-2 text-[10px] font-bold uppercase tracking-wider"
                      style={{ color: "var(--primary-color, #dc2626)" }}
                    >
                      Read Full Text →
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-500">
                Use the{" "}
                <strong className="text-slate-800">Clip & Share</strong> button
                in the top bar to crop and share any article on this page with{" "}
                <strong className="text-slate-800">{tenant?.name}</strong>{" "}
                branding.
              </div>
            )}
          </div>

          {/* Sidebar Monetization Ad Unit */}
          <div className="mt-auto pt-4 border-t border-slate-200">
            <div className="rounded-xl bg-slate-100 border border-dashed border-slate-300 p-4 text-center">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 block mb-1">
                Advertisement • Slot #{tenant?.monetization_settings?.sidebar_ad_slot || "SIDE-300x250"}
              </span>
              <p className="text-xs font-bold text-slate-700">
                {tenant?.name} Digital Subscriptions
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                Get instant morning WhatsApp delivery & ad-free archive access.
              </p>
            </div>
            <p className="text-[11px] text-slate-400 mt-3 leading-relaxed">
              {tenant?.copyright_text}
            </p>
          </div>
        </aside>
      </div>

      {/* 5. Mobile Bottom Navigation Dock (Page Jumper, Prev/Next, Zoom, Clip, Thumbnails) */}
      <nav className="md:hidden bg-slate-950 text-white border-t border-slate-800 px-2 py-2 flex items-center justify-around z-40 shrink-0">
        <button
          onClick={() => goToPage(currentPageIdx - 1)}
          disabled={!issue || currentPageIdx <= 0}
          className="flex flex-col items-center gap-0.5 px-2 py-1 disabled:opacity-35"
        >
          <ChevronLeft className="w-5 h-5" />
          <span className="text-[10px] font-bold">Prev</span>
        </button>

        <button
          onClick={() => setShowMobileThumbs(true)}
          className="flex flex-col items-center gap-0.5 px-2.5 py-1 rounded-lg bg-slate-800"
        >
          <Grid className="w-4 h-4 text-amber-400" />
          <span className="text-[10px] font-bold">
            Page {currentPage?.page_number || 1}/{issue?.pages?.length || 1}
          </span>
        </button>

        <button
          onClick={() => setIsCropMode((prev) => !prev)}
          className="flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg text-white font-bold"
          style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
        >
          <Scissors className="w-4 h-4" />
          <span className="text-[10px]">Clip</span>
        </button>

        <button
          onClick={() => setZoomLevel((z) => (z > 1.2 ? 1.0 : 2.0))}
          className="flex flex-col items-center gap-0.5 px-2 py-1"
        >
          <Maximize2 className="w-4 h-4" />
          <span className="text-[10px] font-bold">
            {zoomLevel > 1.2 ? "Fit" : "2x Zoom"}
          </span>
        </button>

        <button
          onClick={() => goToPage(currentPageIdx + 1)}
          disabled={!issue || currentPageIdx >= (issue?.pages?.length || 1) - 1}
          className="flex flex-col items-center gap-0.5 px-2 py-1 disabled:opacity-35"
        >
          <ChevronRight className="w-5 h-5" />
          <span className="text-[10px] font-bold">Next</span>
        </button>
      </nav>

      {/* Mobile Thumbnails Drawer */}
      {showMobileThumbs && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-xs flex flex-col justify-end md:hidden">
          <div className="bg-slate-900 border-t border-slate-800 rounded-t-2xl p-4 max-h-[75vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white">
                Jump to Page ({issue?.edition_name})
              </h3>
              <button
                onClick={() => setShowMobileThumbs(false)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {issue?.pages?.map((p, idx) => (
                <button
                  key={p.id}
                  onClick={() => {
                    goToPage(idx);
                    setShowMobileThumbs(false);
                  }}
                  className={`rounded-lg overflow-hidden border-2 flex flex-col ${
                    idx === currentPageIdx
                      ? "border-brand-primary"
                      : "border-slate-700"
                  }`}
                >
                  {p.thumbnail_url && (
                    <img
                      src={p.thumbnail_url}
                      alt={`Page ${p.page_number}`}
                      className="w-full aspect-[2/3] object-cover"
                    />
                  )}
                  <span className="text-xs font-bold text-white py-1 text-center bg-slate-800 w-full">
                    Page {p.page_number}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 6. Branded Article Clip Preview, Download & Instant WhatsApp Share Modal */}
      {clipResult && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl border border-slate-200 flex flex-col max-h-[90vh]">
            <div
              className="px-5 py-3.5 text-white flex items-center justify-between"
              style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
            >
              <div className="flex items-center gap-2">
                <Scissors className="w-5 h-5" />
                <div>
                  <h3 className="font-extrabold text-sm sm:text-base">
                    {clipResult.tenant_name} • Branded Article Clipping
                  </h3>
                  <p className="text-[11px] opacity-90">
                    {clipResult.edition_name} • {clipResult.publication_date} • Page{" "}
                    {clipResult.page_number}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setClipResult(null)}
                className="p-1 rounded-lg bg-black/20 hover:bg-black/30 text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 bg-slate-100 overflow-y-auto flex-1 flex items-center justify-center">
              <img
                src={clipResult.clip_url}
                alt="Branded Newspaper Clip"
                className="max-h-[58vh] w-auto object-contain rounded-lg shadow-md border border-slate-300 bg-white"
              />
            </div>

            <div className="p-4 bg-white border-t border-slate-200 flex flex-wrap items-center justify-between gap-2">
              <a
                href={`https://api.whatsapp.com/send?text=${encodeURIComponent(
                  `${clipResult.share_text}\n${
                    typeof window !== "undefined" ? window.location.origin : ""
                  }${clipResult.clip_url}`
                )}`}
                target="_blank"
                rel="noreferrer"
                className="flex-1 bg-[#25D366] hover:bg-[#1EBE5D] text-white font-bold text-xs sm:text-sm py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 shadow transition"
              >
                <Share2 className="w-4 h-4" />
                <span>Share on WhatsApp</span>
              </a>

              <a
                href={clipResult.clip_url}
                download={`${tenant?.slug || "clip"}_p${clipResult.page_number}_${clipResult.clip_id}.jpg`}
                className="bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs sm:text-sm py-2.5 px-4 rounded-xl flex items-center justify-center gap-2 transition"
              >
                <Download className="w-4 h-4" />
                <span>Download Image</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* 7. Smart Article Text Reader Modal */}
      {activeArticleModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200">
            <div
              className="px-5 py-3.5 text-white flex items-center justify-between"
              style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
            >
              <span className="text-xs font-extrabold uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-4 h-4" />
                <span>{tenant?.name} • Digital Article View</span>
              </span>
              <button
                onClick={() => setActiveArticleModal(null)}
                className="p-1 rounded-lg bg-black/20 hover:bg-black/30 text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6">
              <h2 className="text-lg sm:text-xl font-black text-slate-900 leading-snug">
                {activeArticleModal.title}
              </h2>
              <p className="text-xs font-bold text-slate-400 uppercase mt-1 mb-4">
                {issue?.edition_name} • {issue?.publication_date} • Page{" "}
                {currentPage?.page_number}
              </p>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
                {activeArticleModal.content_text}
              </p>
              <div className="mt-6 pt-4 border-t border-slate-200 flex justify-end gap-2">
                <button
                  onClick={() => {
                    const coords = activeArticleModal.coordinates;
                    setActiveArticleModal(null);
                    handleCropComplete(coords);
                  }}
                  className="px-4 py-2 rounded-xl text-white font-bold text-xs flex items-center gap-1.5 cursor-pointer"
                  style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
                >
                  <Scissors className="w-4 h-4" />
                  <span>Generate Branded Clip of Story</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 8. Archive Calendar Modal */}
      {showArchiveModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/75 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200">
            <div
              className="px-5 py-3.5 text-white flex items-center justify-between"
              style={{ backgroundColor: "var(--primary-color, #dc2626)" }}
            >
              <span className="text-sm font-extrabold flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                <span>{tenant?.name} • Past Issues Archive</span>
              </span>
              <button
                onClick={() => setShowArchiveModal(false)}
                className="p-1 rounded-lg bg-black/20 hover:bg-black/30 text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 max-h-[70vh] overflow-y-auto grid grid-cols-2 sm:grid-cols-3 gap-3">
              {archiveDates.map((item) => (
                <button
                  key={item.issue_id}
                  onClick={() => {
                    setSelectedDate(item.publication_date);
                    setShowArchiveModal(false);
                  }}
                  className="border border-slate-200 hover:border-brand-primary rounded-xl p-2.5 flex flex-col items-center text-center group transition cursor-pointer bg-slate-50 hover:bg-white"
                >
                  {item.thumbnail_url && (
                    <img
                      src={item.thumbnail_url}
                      alt={item.publication_date}
                      className="w-24 aspect-[2/3] object-cover rounded shadow-xs mb-2"
                    />
                  )}
                  <span className="text-xs font-extrabold text-slate-900 group-hover:text-brand-primary">
                    {item.publication_date}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {item.edition_name} ({item.page_count}p)
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
