"use client";

import React, { createContext, useContext, useEffect, useState } from "react";

export interface EditionItem {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  display_order: number;
  is_active: boolean;
}

export interface TenantConfig {
  id: string;
  name: string;
  slug: string;
  custom_domains: string[];
  logo_url?: string | null;
  favicon_url?: string | null;
  brand_primary_color: string;
  brand_secondary_color: string;
  header_title?: string | null;
  footer_text?: string | null;
  copyright_text?: string | null;
  monetization_settings: {
    adsense_client_id?: string;
    auto_ads?: boolean;
    header_ad_slot?: string;
    sidebar_ad_slot?: string;
    bottom_ad_slot?: string;
    custom_header_banner_url?: string;
    custom_header_link?: string;
  };
  status: string;
  editions: EditionItem[];
}

export interface TenantSummary {
  id: string;
  name: string;
  slug: string;
  custom_domains: string[];
  brand_primary_color: string;
  brand_secondary_color: string;
  header_title?: string;
  status: string;
}

interface TenantContextValue {
  tenant: TenantConfig | null;
  allTenants: TenantSummary[];
  activeTenantSlug: string | null;
  singleTenantMode: boolean;
  switchTenant: (slug: string) => void;
  refreshTenantConfig: () => Promise<void>;
  loading: boolean;
}

const TenantContext = createContext<TenantContextValue>({
  tenant: null,
  allTenants: [],
  activeTenantSlug: null,
  singleTenantMode: false,
  switchTenant: () => {},
  refreshTenantConfig: async () => {},
  loading: true,
});

export function useTenant() {
  return useContext(TenantContext);
}

export function TenantProvider({
  initialTenant,
  children,
}: {
  initialTenant: TenantConfig | null;
  children: React.ReactNode;
}) {
  const [tenant, setTenant] = useState<TenantConfig | null>(initialTenant);
  const [allTenants, setAllTenants] = useState<TenantSummary[]>([]);
  const [activeTenantSlug, setActiveTenantSlug] = useState<string | null>(
    initialTenant?.slug || null
  );
  const [singleTenantMode, setSingleTenantMode] = useState<boolean>(
    Boolean(process.env.NEXT_PUBLIC_SINGLE_TENANT_SLUG)
  );
  const [loading, setLoading] = useState<boolean>(!initialTenant);

  const applyThemeVariables = (cfg: TenantConfig) => {
    if (typeof document === "undefined") return;
    document.documentElement.style.setProperty(
      "--primary-color",
      cfg.brand_primary_color || "#dc2626"
    );
    document.documentElement.style.setProperty(
      "--secondary-color",
      cfg.brand_secondary_color || "#0f172a"
    );
    if (cfg.header_title || cfg.name) {
      document.title = cfg.header_title || `${cfg.name} Digital E-Paper`;
    }
  };

  const fetchTenantConfig = async (slugOverride?: string | null) => {
    try {
      setLoading(true);
      const headers: Record<string, string> = {};
      if (slugOverride) {
        headers["x-tenant-slug"] = slugOverride;
      }
      const [cfgRes, listRes] = await Promise.all([
        fetch(`/api/v1/public/config${slugOverride ? `?tenant=${slugOverride}` : ""}`, {
          headers,
          cache: "no-store",
        }),
        fetch("/api/v1/public/tenants", { cache: "no-store" }),
      ]);

      if (cfgRes.ok) {
        const cfg: TenantConfig = await cfgRes.json();
        setTenant(cfg);
        setActiveTenantSlug(cfg.slug);
        applyThemeVariables(cfg);
      }
      if (listRes.ok) {
        const list: TenantSummary[] = await listRes.json();
        setAllTenants(list);
      }
    } catch (e) {
      console.error("Failed to fetch tenant config:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const searchParams =
      typeof window !== "undefined"
        ? new URLSearchParams(window.location.search)
        : null;

    if (searchParams?.get("single") === "1" || process.env.NEXT_PUBLIC_SINGLE_TENANT_SLUG) {
      setSingleTenantMode(true);
    }

    const savedSlug =
      process.env.NEXT_PUBLIC_SINGLE_TENANT_SLUG ||
      searchParams?.get("tenant") ||
      (typeof window !== "undefined"
        ? localStorage.getItem("epaper_selected_tenant")
        : null);

    if (savedSlug && savedSlug !== initialTenant?.slug) {
      fetchTenantConfig(savedSlug);
    } else {
      if (initialTenant) {
        applyThemeVariables(initialTenant);
      }
      fetchTenantConfig(initialTenant?.slug || null);
    }
  }, []);

  const switchTenant = (slug: string) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("epaper_selected_tenant", slug);
    }
    setActiveTenantSlug(slug);
    fetchTenantConfig(slug);
  };

  const refreshTenantConfig = async () => {
    await fetchTenantConfig(activeTenantSlug);
  };

  return (
    <TenantContext.Provider
      value={{
        tenant,
        allTenants,
        activeTenantSlug,
        singleTenantMode,
        switchTenant,
        refreshTenantConfig,
        loading,
      }}
    >
      {tenant?.monetization_settings?.auto_ads &&
        tenant?.monetization_settings?.adsense_client_id && (
          <script
            async
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${tenant.monetization_settings.adsense_client_id}`}
            crossOrigin="anonymous"
          />
        )}
      {children}
    </TenantContext.Provider>
  );
}
