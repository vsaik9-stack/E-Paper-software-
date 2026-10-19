import React from "react";
import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";
import { TenantConfig, TenantProvider } from "@/components/TenantProvider";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL || "http://127.0.0.1:8000";

async function getServerSideTenantConfig(): Promise<TenantConfig | null> {
  try {
    const reqHeaders = headers();
    const host =
      reqHeaders.get("x-tenant-domain") ||
      reqHeaders.get("x-forwarded-host") ||
      reqHeaders.get("host") ||
      "localhost:3000";

    const res = await fetch(`${BACKEND_INTERNAL_URL}/api/v1/public/config`, {
      headers: {
        "x-tenant-domain": host,
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const tenant = await getServerSideTenantConfig();
  return {
    title:
      tenant?.header_title ||
      (tenant?.name
        ? `${tenant.name} • Digital E-Paper`
        : "PressGrid White-Label E-Paper SaaS Platform"),
    description:
      tenant?.footer_text ||
      "High-Resolution 300-DPI DeepZoom Multi-Tenant Digital E-Paper Reader",
  };
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const initialTenant = await getServerSideTenantConfig();
  const primaryColor = initialTenant?.brand_primary_color || "#dc2626";
  const secondaryColor = initialTenant?.brand_secondary_color || "#0f172a";

  return (
    <html
      lang="en"
      style={
        {
          "--primary-color": primaryColor,
          "--secondary-color": secondaryColor,
        } as React.CSSProperties
      }
    >
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <TenantProvider initialTenant={initialTenant}>{children}</TenantProvider>
      </body>
    </html>
  );
}
