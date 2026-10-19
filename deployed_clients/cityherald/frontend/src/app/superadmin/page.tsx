"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Eye,
  EyeOff,
  FolderGit2,
  Globe,
  HardDrive,
  KeyRound,
  Lock,
  Plus,
  Rocket,
  Server,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import { useTenant } from "@/components/TenantProvider";

export default function SuperAdminFleetControlPlanePage() {
  const { switchTenant, refreshTenantConfig } = useTenant();

  const [token, setToken] = useState<string>("");
  const [fleetData, setFleetData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [revealedPasswords, setRevealedPasswords] = useState<Record<string, boolean>>({});
  const [inspectModal, setInspectModal] = useState<any>(null);
  const [activeLogModal, setActiveLogModal] = useState<any>(null);

  // Provisioning Form State
  const [clientName, setClientName] = useState<string>("");
  const [clientSlug, setClientSlug] = useState<string>("");
  const [domain, setDomain] = useState<string>("");
  const [logoUrl, setLogoUrl] = useState<string>("");
  const [primaryColor, setPrimaryColor] = useState<string>("#dc2626");
  const [editionsCsv, setEditionsCsv] = useState<string>(
    "Main Edition, Metro Edition, District Supplement"
  );
  const [adminEmail, setAdminEmail] = useState<string>("");
  const [adminPassword, setAdminPassword] = useState<string>("Editor@2026");

  // Deployment Mode: "LOCAL_VPS" vs "REMOTE_DEDICATED_VPS"
  const [deploymentMode, setDeploymentMode] = useState<
    "LOCAL_VPS" | "REMOTE_DEDICATED_VPS"
  >("LOCAL_VPS");
  const [monthlyPrice, setMonthlyPrice] = useState<number>(6500);

  // Dedicated VPS SSH Credentials (kept strictly with us)
  const [vpsProvider, setVpsProvider] = useState<string>(
    "Hetzner Cloud Dedicated VPS"
  );
  const [vpsIp, setVpsIp] = useState<string>("");
  const [vpsSshPort, setVpsSshPort] = useState<number>(22);
  const [vpsSshUser, setVpsSshUser] = useState<string>("root");
  const [vpsRootPassword, setVpsRootPassword] = useState<string>("");

  const [provisioning, setProvisioning] = useState<boolean>(false);
  const [provisionSuccess, setProvisionSuccess] = useState<any>(null);

  useEffect(() => {
    const initSuperAdmin = async () => {
      let jwt = localStorage.getItem("epaper_jwt_token");
      if (!jwt) {
        const res = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: "superadmin@platform.com",
            password: "Admin@123",
          }),
        });
        if (res.ok) {
          const data = await res.json();
          jwt = data.access_token;
          localStorage.setItem("epaper_jwt_token", jwt!);
        }
      }
      if (jwt) {
        setToken(jwt);
        await fetchFleet(jwt);
      }
    };
    initSuperAdmin();
  }, []);

  const fetchFleet = async (jwtToken: string) => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/fleet/instances", {
        headers: { Authorization: `Bearer ${jwtToken}` },
        cache: "no-store",
      });
      if (res.ok) {
        setFleetData(await res.json());
      }
    } finally {
      setLoading(false);
    }
  };

  const handleProvisionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!clientName || !domain || !token) return;
    setProvisioning(true);
    setProvisionSuccess(null);

    try {
      const cleanSlug =
        clientSlug || clientName.toLowerCase().replace(/[^a-z0-9]+/g, "");
      const res = await fetch("/api/v1/fleet/provision", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          client_name: clientName,
          client_slug: cleanSlug,
          domain: domain.trim(),
          logo_url: logoUrl.trim() || null,
          brand_primary_color: primaryColor,
          brand_secondary_color: "#0f172a",
          editions: editionsCsv
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
          admin_email:
            adminEmail.trim() ||
            `editor@${domain.trim().replace(/^epaper\./, "")}`,
          admin_password: adminPassword,
          deployment_mode: deploymentMode,
          plan_name:
            deploymentMode === "REMOTE_DEDICATED_VPS"
              ? "Enterprise Multi-Edition Dedicated VPS"
              : "Standard Shared VPS (Docker Folder)",
          monthly_price_inr: monthlyPrice,
          vps_provider:
            deploymentMode === "REMOTE_DEDICATED_VPS"
              ? vpsProvider
              : "Our Primary Shared VPS",
          vps_ip:
            deploymentMode === "REMOTE_DEDICATED_VPS" ? vpsIp.trim() : "127.0.0.1",
          vps_ssh_port: vpsSshPort,
          vps_ssh_user: vpsSshUser,
          vps_root_password:
            deploymentMode === "REMOTE_DEDICATED_VPS" ? vpsRootPassword : null,
        }),
      });

      if (res.ok) {
        const result = await res.json();
        setProvisionSuccess(result);
        setClientName("");
        setClientSlug("");
        setDomain("");
        setVpsIp("");
        setVpsRootPassword("");
        await fetchFleet(token);
        await refreshTenantConfig();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to provision client instance");
      }
    } finally {
      setProvisioning(false);
    }
  };

  const handleInspectFiles = async (instanceId: string) => {
    const res = await fetch(`/api/v1/fleet/instances/${instanceId}/files`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      setInspectModal(await res.json());
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center gap-1.5 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Reader</span>
          </Link>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-tight text-white">
                Master VPS Fleet & White-Label Instance Provisioner
              </h1>
              <p className="text-xs text-slate-400">
                1-Click Isolated Client Folder/Docker Generator + Dedicated Remote VPS SSH Vault (Credentials Visible Only to You)
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl w-full mx-auto p-6 flex flex-col gap-6">
        {/* Top Summary KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase text-slate-400">
              Total Provisioned Newspapers
            </span>
            <p className="text-3xl font-black text-white mt-1">
              {fleetData?.summary?.total_instances || 0}
            </p>
            <span className="text-[11px] text-slate-400">
              Isolated Branded Packages
            </span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase text-slate-400">
              Tier 1: Shared VPS Folders
            </span>
            <p className="text-3xl font-black text-emerald-400 mt-1">
              {fleetData?.summary?.local_vps_containers || 0}
            </p>
            <span className="text-[11px] text-slate-400">
              Hosted in <code>deployed_clients/&lt;slug&gt;/</code>
            </span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase text-slate-400">
              Tier 2: Dedicated Remote VPS
            </span>
            <p className="text-3xl font-black text-amber-400 mt-1">
              {fleetData?.summary?.remote_dedicated_vps || 0}
            </p>
            <span className="text-[11px] text-slate-400">
              Heavy Multi-Edition Clients (SSH Vault)
            </span>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase text-slate-400">
              Monthly Recurring Revenue
            </span>
            <p className="text-3xl font-black text-indigo-400 mt-1">
              ₹{(fleetData?.summary?.monthly_recurring_revenue_inr || 0).toLocaleString()}
              <span className="text-sm font-normal text-slate-400">/mo</span>
            </p>
            <span className="text-[11px] text-emerald-400 font-semibold">
              Active SaaS Subscriptions
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* LEFT 7 COLUMNS: Deployed Newspaper Fleet & Owner-Only VPS SSH Password Vault */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
                <h2 className="font-black text-base flex items-center gap-2">
                  <Server className="w-4 h-4 text-indigo-400" />
                  <span>Provisioned Newspaper Clients & VPS Vault</span>
                </h2>
                <span className="text-xs text-slate-400">
                  All folders in <code>./deployed_clients/</code>
                </span>
              </div>

              <div className="divide-y divide-slate-800">
                {fleetData?.instances?.map((inst: any) => {
                  const isDedicated =
                    inst.deployment_mode === "REMOTE_DEDICATED_VPS";
                  const showPass = Boolean(revealedPasswords[inst.id]);

                  return (
                    <div
                      key={inst.id}
                      className="p-5 flex flex-col gap-3.5 hover:bg-slate-800/30 transition"
                    >
                      {/* Top Row: Client Identity & Deployment Tier Badge */}
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex items-center gap-3.5">
                          <div
                            className="w-11 h-11 rounded-xl flex items-center justify-center text-white font-black text-lg shadow"
                            style={{ backgroundColor: inst.brand_primary_color }}
                          >
                            {inst.client_name.charAt(0)}
                          </div>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="font-black text-base text-white">
                                {inst.client_name}
                              </h3>
                              <span className="px-2 py-0.5 rounded bg-slate-800 text-sky-400 font-mono text-xs flex items-center gap-1">
                                <Globe className="w-3 h-3" />
                                {inst.domain}
                              </span>
                              {isDedicated ? (
                                <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-300 text-[10px] font-black uppercase">
                                  Dedicated Remote VPS (Multi-Edition)
                                </span>
                              ) : (
                                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-[10px] font-black uppercase">
                                  Shared VPS Docker Folder (Port {inst.assigned_port})
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-400 mt-1">
                              Editions ({inst.editions_list?.length || 1}):{" "}
                              <span className="text-slate-200 font-semibold">
                                {inst.editions_list?.join(" • ")}
                              </span>
                            </p>
                          </div>
                        </div>

                        <div className="text-right">
                          <span className="text-sm font-black text-emerald-400">
                            ₹{(inst.monthly_price_inr || 0).toLocaleString()}/mo
                          </span>
                          <p className="text-[10px] text-slate-400">
                            {inst.plan_name}
                          </p>
                        </div>
                      </div>

                      {/* Middle Box: Physical VPS Folder + Client Admin Login + Owner-Only VPS Root Password */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-slate-950/90 border border-slate-800/90 rounded-xl p-3.5 text-xs">
                        <div>
                          <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">
                            Client Handover Details (Give to Newspaper Client)
                          </span>
                          <div className="text-slate-300">
                            <strong>Uploader URL:</strong>{" "}
                            <code className="text-amber-300">
                              https://{inst.domain}/admin
                            </code>
                          </div>
                          <div className="text-slate-300 mt-0.5">
                            <strong>Editor Login:</strong>{" "}
                            <code>{inst.admin_email}</code> /{" "}
                            <code>{inst.admin_password_plain}</code>
                          </div>
                        </div>

                        <div className="border-t md:border-t-0 md:border-l border-slate-800 pt-2 md:pt-0 md:pl-3">
                          <span className="text-[10px] font-bold uppercase text-indigo-400 flex items-center gap-1 mb-1">
                            <Lock className="w-3 h-3" />
                            <span>Our Private VPS Credentials Vault</span>
                          </span>
                          {isDedicated ? (
                            <>
                              <div className="text-slate-300">
                                <strong>Dedicated VPS IP:</strong>{" "}
                                <code className="text-emerald-400">
                                  {inst.vps_ssh_user}@{inst.vps_ip}:{inst.vps_ssh_port}
                                </code>{" "}
                                ({inst.vps_provider})
                              </div>
                              <div className="text-slate-300 mt-0.5 flex items-center gap-2">
                                <strong>VPS Root Pass:</strong>
                                <code className="bg-slate-900 px-1.5 py-0.5 rounded text-rose-300">
                                  {showPass
                                    ? inst.vps_root_password || "SSH-Key"
                                    : "••••••••••••••••"}
                                </code>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setRevealedPasswords((p) => ({
                                      ...p,
                                      [inst.id]: !p[inst.id],
                                    }))
                                  }
                                  className="text-slate-400 hover:text-white cursor-pointer"
                                  title="Reveal/Hide VPS Root Password"
                                >
                                  {showPass ? (
                                    <EyeOff className="w-3.5 h-3.5" />
                                  ) : (
                                    <Eye className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="text-slate-300 truncate">
                                <strong>VPS Folder:</strong>{" "}
                                <code className="text-slate-400">
                                  deployed_clients/{inst.client_slug}/
                                </code>
                              </div>
                              <div className="text-slate-300 mt-0.5">
                                <strong>Docker Stack:</strong>{" "}
                                <code>
                                  epaper_api_{inst.client_slug} (:{inst.assigned_port})
                                </code>
                              </div>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Bottom Row: Action Buttons */}
                      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleInspectFiles(inst.id)}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center gap-1.5 transition cursor-pointer"
                          >
                            <FolderGit2 className="w-3.5 h-3.5 text-sky-400" />
                            <span>Inspect Generated Folder & Docker Files</span>
                          </button>
                          <button
                            onClick={() => setActiveLogModal(inst)}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold flex items-center gap-1.5 transition cursor-pointer"
                          >
                            <Terminal className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Deployment Logs</span>
                          </button>
                        </div>

                        <div className="flex items-center gap-2">
                          <Link
                            href={`/?tenant=${inst.client_slug}&single=1`}
                            onClick={() => switchTenant(inst.client_slug)}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition"
                          >
                            Open Client Reader
                          </Link>
                          <Link
                            href={`/admin?tenant=${inst.client_slug}&single=1`}
                            onClick={() => switchTenant(inst.client_slug)}
                            className="px-3.5 py-1.5 rounded-lg text-white text-xs font-bold transition shadow"
                            style={{ backgroundColor: inst.brand_primary_color }}
                          >
                            Open Client Uploader (/admin) →
                          </Link>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* RIGHT 5 COLUMNS: 1-Click Client Folder / Remote Dedicated VPS Provisioner */}
          <div className="lg:col-span-5">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sticky top-6">
              <h2 className="text-base font-black text-white flex items-center gap-2 mb-1">
                <Rocket className="w-5 h-5 text-indigo-400" />
                <span>Provision New Newspaper Subscription</span>
              </h2>
              <p className="text-xs text-slate-400 mb-5">
                Point client DNS (<code>epaper.domain.com</code>) → Choose Shared VPS Folder or Dedicated Remote VPS → Auto-build package with our core engine, their logo & colors, and hand over their <code>/admin</code> uploader!
              </p>

              {provisionSuccess && (
                <div className="mb-5 p-4 rounded-xl bg-emerald-500/15 border border-emerald-500/40 text-emerald-200 text-xs flex flex-col gap-2">
                  <div className="font-black text-sm text-emerald-300 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>
                      Client Folder & Core Engine Provisioned!
                    </span>
                  </div>
                  <div>
                    <strong>VPS Folder Created:</strong>{" "}
                    <code className="bg-slate-950 px-1.5 py-0.5 rounded">
                      {provisionSuccess.local_folder_path}
                    </code>
                  </div>
                  <div>
                    <strong>Client Admin Login:</strong>{" "}
                    <code>{provisionSuccess.admin_email}</code> /{" "}
                    <code>{provisionSuccess.admin_password}</code>
                  </div>
                  <div className="flex gap-2 mt-1">
                    <Link
                      href={`/admin?tenant=${provisionSuccess.client_slug}&single=1`}
                      className="px-3 py-1.5 rounded-lg bg-emerald-600 text-white font-bold"
                    >
                      Open Their /admin Uploader →
                    </Link>
                    <Link
                      href={`/?tenant=${provisionSuccess.client_slug}&single=1`}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 text-white font-bold"
                    >
                      Open Their Reader →
                    </Link>
                  </div>
                </div>
              )}

              <form
                onSubmit={handleProvisionSubmit}
                className="flex flex-col gap-4 text-xs"
              >
                {/* Step 1: Choose Hosting Tier */}
                <div>
                  <label className="block font-bold uppercase text-slate-400 mb-1.5">
                    1. Select Hosting Tier (Shared VPS Folder vs Dedicated VPS)
                  </label>
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      type="button"
                      onClick={() => {
                        setDeploymentMode("LOCAL_VPS");
                        setMonthlyPrice(6500);
                      }}
                      className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                        deploymentMode === "LOCAL_VPS"
                          ? "bg-indigo-600/20 border-indigo-500 text-white"
                          : "bg-slate-950 border-slate-800 text-slate-400"
                      }`}
                    >
                      <div className="font-black text-xs flex items-center gap-1.5">
                        <HardDrive className="w-4 h-4 text-emerald-400" />
                        <span>Our Shared VPS</span>
                      </div>
                      <p className="text-[10px] mt-1 opacity-80">
                        Creates Docker folder on our VPS (1–3 editions)
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setDeploymentMode("REMOTE_DEDICATED_VPS");
                        setMonthlyPrice(18500);
                      }}
                      className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                        deploymentMode === "REMOTE_DEDICATED_VPS"
                          ? "bg-amber-500/20 border-amber-500 text-white"
                          : "bg-slate-950 border-slate-800 text-slate-400"
                      }`}
                    >
                      <div className="font-black text-xs flex items-center gap-1.5">
                        <Server className="w-4 h-4 text-amber-400" />
                        <span>Separate Dedicated VPS</span>
                      </div>
                      <p className="text-[10px] mt-1 opacity-80">
                        Heavy client (many editions). SSHs into new VPS!
                      </p>
                    </button>
                  </div>
                </div>

                {/* Step 2: Newspaper Identity & DNS Domain */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      Newspaper Name
                    </label>
                    <input
                      type="text"
                      value={clientName}
                      onChange={(e) => {
                        setClientName(e.target.value);
                        const s = e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]+/g, "");
                        setClientSlug(s);
                        if (s) setDomain(`epaper.${s}.com`);
                      }}
                      placeholder="e.g. Vaartha Daily"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white text-sm"
                      required
                    />
                  </div>

                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      DNS Subdomain (Pointed to VPS)
                    </label>
                    <input
                      type="text"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                      placeholder="epaper.vaartha.com"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-sky-400 text-sm font-mono"
                      required
                    />
                  </div>
                </div>

                {/* Branding & Editions */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      Brand Primary Color
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={primaryColor}
                        onChange={(e) => setPrimaryColor(e.target.value)}
                        className="h-9 w-12 rounded bg-slate-950 border border-slate-800 cursor-pointer"
                      />
                      <input
                        type="text"
                        value={primaryColor}
                        onChange={(e) => setPrimaryColor(e.target.value)}
                        className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      Client Logo URL (Optional)
                    </label>
                    <input
                      type="text"
                      value={logoUrl}
                      onChange={(e) => setLogoUrl(e.target.value)}
                      placeholder="https://.../logo.png"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-bold uppercase text-slate-400 mb-1">
                    Editions to Pre-Configure (Comma Separated)
                  </label>
                  <input
                    type="text"
                    value={editionsCsv}
                    onChange={(e) => setEditionsCsv(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white"
                  />
                </div>

                {/* Step 3: Client Admin Uploader Credentials */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-slate-800">
                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      Client Admin Email (for /admin)
                    </label>
                    <input
                      type="email"
                      value={adminEmail}
                      onChange={(e) => setAdminEmail(e.target.value)}
                      placeholder={`editor@${domain.replace(/^epaper\./, "") || "domain.com"}`}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="block font-bold uppercase text-slate-400 mb-1">
                      Client Admin Password
                    </label>
                    <input
                      type="text"
                      value={adminPassword}
                      onChange={(e) => setAdminPassword(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-amber-300 font-mono"
                    />
                  </div>
                </div>

                {/* Step 4: Dedicated Remote VPS SSH Credentials (Only when Separate VPS is selected) */}
                {deploymentMode === "REMOTE_DEDICATED_VPS" && (
                  <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col gap-3">
                    <div className="flex items-center gap-1.5 text-amber-300 font-black text-xs">
                      <KeyRound className="w-4 h-4" />
                      <span>
                        Dedicated VPS SSH Credentials (Stored Only in Our Master Vault)
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                      <div>
                        <label className="block font-bold uppercase text-slate-400 mb-1">
                          VPS Provider / Spec
                        </label>
                        <input
                          type="text"
                          value={vpsProvider}
                          onChange={(e) => setVpsProvider(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white"
                        />
                      </div>
                      <div>
                        <label className="block font-bold uppercase text-slate-400 mb-1">
                          Dedicated VPS IPv4 Address
                        </label>
                        <input
                          type="text"
                          value={vpsIp}
                          onChange={(e) => setVpsIp(e.target.value)}
                          placeholder="e.g. 65.108.142.99"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-emerald-400 font-mono"
                          required
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2.5">
                      <div>
                        <label className="block font-bold uppercase text-slate-400 mb-1">
                          SSH User
                        </label>
                        <input
                          type="text"
                          value={vpsSshUser}
                          onChange={(e) => setVpsSshUser(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block font-bold uppercase text-slate-400 mb-1">
                          SSH Port
                        </label>
                        <input
                          type="number"
                          value={vpsSshPort}
                          onChange={(e) => setVpsSshPort(Number(e.target.value))}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block font-bold uppercase text-slate-400 mb-1">
                          Root Password
                        </label>
                        <input
                          type="password"
                          value={vpsRootPassword}
                          onChange={(e) => setVpsRootPassword(e.target.value)}
                          placeholder="VPS Root Pass"
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-rose-300 font-mono"
                          required
                        />
                      </div>
                    </div>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={provisioning}
                  className="mt-1 py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-sm flex items-center justify-center gap-2 shadow-lg cursor-pointer disabled:opacity-50"
                >
                  <Plus className="w-4 h-4" />
                  <span>
                    {provisioning
                      ? "Building Isolated Client Folder & Core Engine..."
                      : deploymentMode === "REMOTE_DEDICATED_VPS"
                      ? "Build Client Package & Deploy to Dedicated VPS"
                      : "Create Client Folder on Shared VPS & Launch"}
                  </span>
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>

      {/* Modal 1: Inspect Generated Client Folder Files (`brand_config.json`, `docker-compose.yml`, `Caddyfile`, `deploy_to_vps.sh`) */}
      {inspectModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full max-h-[88vh] flex flex-col overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="font-black text-base text-white">
                  Isolated Client Package: {inspectModal.client_name}
                </h3>
                <p className="text-xs text-slate-400 font-mono">
                  {inspectModal.local_folder_path}
                </p>
              </div>
              <button
                onClick={() => setInspectModal(null)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex flex-col gap-5 text-xs">
              {Object.entries(inspectModal.files || {}).map(
                ([filename, content]: [string, any]) => (
                  <div key={filename}>
                    <div className="font-mono font-bold text-amber-400 mb-1.5">
                      📄 {filename}
                    </div>
                    <pre className="bg-slate-950 border border-slate-800 rounded-xl p-4 overflow-x-auto text-slate-300 font-mono text-[11px] leading-relaxed">
                      {content}
                    </pre>
                  </div>
                )
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Provisioning Logs */}
      {activeLogModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="font-black text-base text-white flex items-center gap-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span>
                  Provisioning & VPS Logs — {activeLogModal.client_name} (
                  {activeLogModal.domain})
                </span>
              </h3>
              <button
                onClick={() => setActiveLogModal(null)}
                className="p-1.5 rounded-lg bg-slate-800 text-slate-300 hover:text-white cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6">
              <pre className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-emerald-400 font-mono text-xs whitespace-pre-wrap leading-relaxed">
                {activeLogModal.provision_logs}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
