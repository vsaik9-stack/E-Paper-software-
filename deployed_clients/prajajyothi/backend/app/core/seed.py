from datetime import date, timedelta
from typing import Tuple
import pymupdf as fitz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.models.newspaper import ArticleRegion, Edition, Issue, Page
from app.models.tenant import Tenant, TenantUser
from app.pdf.processor import pdf_processor
from app.storage.keys import build_issue_pdf_key, sanitize_slug
from app.storage.service import storage_service


def _hex_to_pdf_color(hex_str: str) -> Tuple[float, float, float]:
    h = hex_str.lstrip("#")
    if len(h) == 6:
        return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)
    return (0.86, 0.15, 0.15)


def generate_sample_newspaper_pdf_bytes(
    newspaper_name: str,
    edition_name: str,
    primary_hex: str,
    pub_date: date,
    num_pages: int = 4,
) -> bytes:
    """
    Generates a crisp multi-page broadsheet newspaper vector PDF using PyMuPDF
    so that our 300-DPI + 512x512 WebP DeepZoom pyramid engine renders ultra-sharp typography!
    """
    doc = fitz.open()
    brand_rgb = _hex_to_pdf_color(primary_hex)
    dark_slate = (0.12, 0.16, 0.23)
    muted_gray = (0.39, 0.45, 0.55)
    light_bg = (0.96, 0.97, 0.98)

    section_titles = [
        "FRONT PAGE • NATIONAL & STATE HEADLINES",
        "METRO & REGIONAL DEVELOPMENTS",
        "BUSINESS, ECONOMY & TECH INNOVATION",
        "SPORTS, CINEMA & EDITORIAL OP-ED",
    ]

    headlines_by_page = [
        [
            (
                f"{newspaper_name} Launches Next-Gen Ultra-Sharp DeepZoom Digital E-Paper Platform",
                "Readers across the globe can now experience zero-blur 300 DPI vector typography, instant 512x512 WebP pyramid tile streaming, and 1-click branded WhatsApp article clipping across mobile and desktop devices.",
            ),
            (
                "High-Speed Metro Rail & Smart Infrastructure Corridor Receives ₹18,500 Crore Approval",
                "The cabinet cleared phase-III expansion connecting major IT hubs, industrial parks, and regional transit terminals with sustainable solar-powered stations and automated signaling.",
            ),
            (
                "Record Monsoon Harvest Boosts Agricultural Exports by 24% Across Southern States",
                "Modernized cold-chain logistics and direct digital procurement portals have enabled farmers to secure premium prices in international markets this quarter.",
            ),
        ],
        [
            (
                f"{edition_name} Civic Body Unveils 24x7 Automated Water Supply & Green Parks Initiative",
                "Over 45 urban wards will transition to smart pressure-monitored distribution pipelines alongside newly developed urban forest walkways and solar street lighting.",
            ),
            (
                "AI-Powered Traffic Management Reduces Peak Hour Commute Times by 31%",
                "Adaptive signal synchronization and real-time commuter alerts have transformed key arterial junctions across the metropolitan region.",
            ),
            (
                "State Universities Partner with Global Tech Leaders for Semiconductor Research Labs",
                "New cleanroom training facilities and VLSI design fellowships will train 5,000 engineering graduates annually.",
            ),
        ],
        [
            (
                "Indian FinTech & Cloud SaaS Exports Cross Historic $95 Billion Milestone",
                "Enterprise adoption of multi-tenant cloud architectures and automated AI workflows continues to drive strong venture capital inflows and domestic job creation.",
            ),
            (
                "Renewable Energy Grid Surpasses 55% Share in Peak Industrial Power Demand",
                "Grid-scale battery storage installations and hybrid wind-solar parks have stabilized industrial tariffs for manufacturing clusters.",
            ),
            (
                "Gold & Equity Markets Rally to Record Highs Amid Strong Quarterly Corporate Earnings",
                "Banking, pharmaceuticals, and precision manufacturing indices led the broad-based rally on institutional buying.",
            ),
        ],
        [
            (
                "Championship Finals: Home Team Clinches Dramatic Last-Over Victory Before 65,000 Fans",
                "A sensational unbeaten century and clinical death-over bowling sealed the trophy in one of the most memorable finals of the decade.",
            ),
            (
                "Editorial: Preserving Journalistic Integrity in the Era of Instant Digital Media",
                "Why trusted broadsheet journalism, verified reporting, and accessible digital editions remain the cornerstone of an informed democratic society.",
            ),
            (
                "Regional Cinema Sweeps National Film Awards with Compelling Rural Drama",
                "Critics praised the authentic cinematography, rooted storytelling, and powerful ensemble performances.",
            ),
        ],
    ]

    for p_idx in range(num_pages):
        # Broadsheet aspect ratio (900 x 1350 pt)
        page = doc.new_page(width=900, height=1350)
        page_num = p_idx + 1
        sec_title = section_titles[p_idx % len(section_titles)]

        # Outer page background & border
        page.draw_rect(fitz.Rect(24, 24, 876, 1326), color=(0.82, 0.85, 0.89), width=1.5)

        if page_num == 1:
            # Grand Broadsheet Masthead on Page 1
            page.draw_rect(fitz.Rect(36, 36, 864, 155), color=brand_rgb, fill=brand_rgb)
            page.insert_text(
                fitz.Point(54, 102),
                newspaper_name.upper(),
                fontsize=48,
                fontname="hebo",
                color=(1, 1, 1),
            )
            page.insert_text(
                fitz.Point(56, 134),
                f"OFFICIAL DIGITAL BROADSHEET • {edition_name.upper()} • {pub_date.strftime('%A, %d %B %Y').upper()}",
                fontsize=13,
                fontname="hebo",
                color=(0.95, 0.95, 0.95),
            )
            page.insert_text(
                fitz.Point(740, 100),
                f"PAGE {page_num} OF {num_pages}",
                fontsize=15,
                fontname="hebo",
                color=(1, 1, 1),
            )
            top_y = 175
        else:
            # Running header on inner pages
            page.draw_rect(fitz.Rect(36, 36, 864, 88), color=brand_rgb, fill=brand_rgb)
            page.insert_text(
                fitz.Point(50, 69),
                f"{newspaper_name.upper()}  |  {sec_title}",
                fontsize=18,
                fontname="hebo",
                color=(1, 1, 1),
            )
            page.insert_text(
                fitz.Point(710, 68),
                f"{pub_date.strftime('%d %b %Y')} • PAGE {page_num}",
                fontsize=14,
                fontname="hebo",
                color=(1, 1, 1),
            )
            top_y = 110

        # Sub-banner strip
        page.draw_rect(fitz.Rect(36, top_y, 864, top_y + 30), color=light_bg, fill=light_bg)
        page.insert_text(
            fitz.Point(48, top_y + 20),
            f"SECTION: {sec_title}   •   EDITION: {edition_name.upper()}   •   300 DPI DEEP-ZOOM VECTOR EDITION",
            fontsize=11,
            fontname="hebo",
            color=dark_slate,
        )

        stories = headlines_by_page[p_idx % len(headlines_by_page)]

        # Lead Story Box (Top Half)
        lead_top = top_y + 46
        lead_rect = fitz.Rect(40, lead_top, 860, lead_top + 430)
        page.draw_rect(lead_rect, color=(0.85, 0.88, 0.92), width=1.2)

        # Category badge
        page.draw_rect(fitz.Rect(56, lead_top + 18, 220, lead_top + 44), color=brand_rgb, fill=brand_rgb)
        page.insert_text(
            fitz.Point(68, lead_top + 36),
            "TOP LEAD STORY",
            fontsize=11,
            fontname="hebo",
            color=(1, 1, 1),
        )

        # Lead Headline
        page.insert_textbox(
            fitz.Rect(56, lead_top + 56, 844, lead_top + 150),
            stories[0][0],
            fontsize=27,
            fontname="hebo",
            color=dark_slate,
        )

        # Simulated photo illustration box inside lead story
        photo_rect = fitz.Rect(56, lead_top + 155, 460, lead_top + 405)
        page.draw_rect(photo_rect, color=brand_rgb, fill=(0.93, 0.95, 0.98), width=1.5)
        page.insert_textbox(
            fitz.Rect(76, lead_top + 235, 440, lead_top + 350),
            f"[ {newspaper_name.upper()} HIGH-RESOLUTION PRESS PHOTOGRAPH ]\n\n{edition_name} Bureau • {pub_date.strftime('%d %B %Y')}\nUse the 'Clip Article' tool in the toolbar to crop and share any region of this broadsheet page with automatic newspaper branding!",
            fontsize=12.5,
            fontname="hebo",
            color=dark_slate,
        )

        # Lead Article Multi-Column Text
        body_text = (
            f"BUREAU REPORT ({edition_name.upper()}): {stories[0][1]}\n\n"
            f"Speaking at the inaugural session today, senior editors and technology architects emphasized that readers demand instant page loads alongside print-grade crispness when zooming into fine print and columns.\n\n"
            f"By combining PyMuPDF 300-DPI vector rasterization with 512x512 WebP DeepZoom tile pyramids and immutable edge caching, {newspaper_name} delivers a seamless broadsheet reading experience across every screen size."
        )
        page.insert_textbox(
            fitz.Rect(480, lead_top + 155, 844, lead_top + 410),
            body_text,
            fontsize=12.5,
            fontname="helv",
            color=(0.18, 0.22, 0.28),
        )

        # Bottom Two-Column Stories
        bottom_top = lead_top + 450
        col1_rect = fitz.Rect(40, bottom_top, 440, 1255)
        col2_rect = fitz.Rect(460, bottom_top, 860, 1255)

        for idx_col, (crect, story) in enumerate([(col1_rect, stories[1]), (col2_rect, stories[2])]):
            page.draw_rect(crect, color=(0.85, 0.88, 0.92), width=1.0)
            page.draw_rect(
                fitz.Rect(crect.x0 + 16, crect.y0 + 16, crect.x0 + 165, crect.y0 + 38),
                color=dark_slate,
                fill=dark_slate,
            )
            page.insert_text(
                fitz.Point(crect.x0 + 26, crect.y0 + 31),
                f"SPECIAL REPORT #{idx_col + 1}",
                fontsize=10,
                fontname="hebo",
                color=(1, 1, 1),
            )
            page.insert_textbox(
                fitz.Rect(crect.x0 + 16, crect.y0 + 48, crect.x1 - 16, crect.y0 + 155),
                story[0],
                fontsize=19,
                fontname="hebo",
                color=brand_rgb if idx_col == 0 else dark_slate,
            )
            extended_body = (
                f"{story[1]}\n\n"
                f" Officials confirmed that implementation timelines have been accelerated across all districts under the {edition_name} jurisdiction. Citizens and industry stakeholders welcomed the transparent dashboard monitoring and real-time public updates.\n\n"
                f"Key Highlights:\n"
                f"• 100% Tenant-Isolated Cloud Architecture\n"
                f"• Instant Custom Domain SSL via Caddy On-Demand TLS\n"
                f"• Interactive 8-Point Crop & Branded WhatsApp Clipping\n"
                f"• Smart Clickable Article Regions & Audio Page Turns"
            )
            page.insert_textbox(
                fitz.Rect(crect.x0 + 16, crect.y0 + 165, crect.x1 - 16, crect.y1 - 20),
                extended_body,
                fontsize=12,
                fontname="helv",
                color=(0.2, 0.24, 0.3),
            )

        # Bottom Footer Strip
        page.draw_rect(fitz.Rect(36, 1272, 864, 1312), color=dark_slate, fill=dark_slate)
        page.insert_text(
            fitz.Point(52, 1297),
            f"© {pub_date.year} {newspaper_name} • {edition_name} • Powered by PressGrid White-Label E-Paper SaaS Engine",
            fontsize=11,
            fontname="hebo",
            color=(1, 1, 1),
        )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def seed_initial_multi_tenant_data(db: AsyncSession):
    """
    Seeds the platform with:
    1. Super-Admin user (`superadmin@platform.com` / `Admin@123`)
    2. Three distinct White-Label Newspaper Tenants:
       - Disha Daily (`dishadaily`, Crimson Red `#dc2626`)
       - Praja Jyothi (`prajajyothi`, Royal Blue `#034ea2`)
       - City Herald (`cityherald`, Emerald Green `#059669`)
    3. Multiple regional editions and rendered 4-page DeepZoom issues with clickable ArticleRegions.
    """
    existing = await db.execute(select(Tenant).limit(1))
    if existing.scalars().first():
        return

    print("🌱 Seeding Multi-Tenant White-Label E-Paper SaaS Platform...")

    # 1. Super Admin User
    superadmin = TenantUser(
        tenant_id=None,
        email="superadmin@platform.com",
        full_name="Platform Super-Admin",
        hashed_password=get_password_hash("Admin@123"),
        role="SUPER_ADMIN",
        is_active=True,
    )
    db.add(superadmin)

    tenants_seed = [
        {
            "name": "Disha Daily",
            "slug": "dishadaily",
            "custom_domains": ["epaper.dishadaily.com", "dishadaily.com", "dishadaily.localhost"],
            "brand_primary_color": "#dc2626",
            "brand_secondary_color": "#0f172a",
            "header_title": "Disha Daily • Official Digital Broadsheet",
            "footer_text": "Disha Daily brings you fearless journalism and ultra-sharp digital broadsheet editions across Telangana & Andhra Pradesh.",
            "copyright_text": "© 2026 Disha Daily Publications Pvt. Ltd. All rights reserved.",
            "admin_email": "editor@dishadaily.com",
            "editions": [
                ("Hyderabad Main", "hyderabad-main"),
                ("Warangal Edition", "warangal"),
                ("Vijayawada Edition", "vijayawada"),
            ],
        },
        {
            "name": "Praja Jyothi",
            "slug": "prajajyothi",
            "custom_domains": ["epaper.prajajyothi.com", "prajajyothi.com", "prajajyothi.localhost"],
            "brand_primary_color": "#034ea2",
            "brand_secondary_color": "#1e293b",
            "header_title": "Praja Jyothi • People's Daily E-Paper",
            "footer_text": "Praja Jyothi Digital Edition — Trusted daily news, regional supplements, and insightful editorials.",
            "copyright_text": "© 2026 Praja Jyothi Media Network. All rights reserved.",
            "admin_email": "editor@prajajyothi.com",
            "editions": [
                ("State Main Edition", "state-main"),
                ("Greater Hyderabad", "greater-hyderabad"),
                ("Visakhapatnam", "visakhapatnam"),
            ],
        },
        {
            "name": "City Herald",
            "slug": "cityherald",
            "custom_domains": ["epaper.cityherald.com", "cityherald.com", "cityherald.localhost"],
            "brand_primary_color": "#059669",
            "brand_secondary_color": "#064e3b",
            "header_title": "The City Herald • Metropolitan Daily",
            "footer_text": "The City Herald — Premier English metropolitan broadsheet covering business, governance, technology, and culture.",
            "copyright_text": "© 2026 The City Herald Publishing Group. All rights reserved.",
            "admin_email": "editor@cityherald.com",
            "editions": [
                ("Metro Financial", "metro-financial"),
                ("National Edition", "national"),
            ],
        },
    ]

    today = date.today()

    for t_data in tenants_seed:
        tenant = Tenant(
            name=t_data["name"],
            slug=t_data["slug"],
            custom_domains=t_data["custom_domains"],
            brand_primary_color=t_data["brand_primary_color"],
            brand_secondary_color=t_data["brand_secondary_color"],
            header_title=t_data["header_title"],
            footer_text=t_data["footer_text"],
            copyright_text=t_data["copyright_text"],
            monetization_settings={
                "adsense_client_id": "ca-pub-9876543210123456",
                "auto_ads": True,
                "header_ad_slot": "1029384756",
                "sidebar_ad_slot": "5647382910",
                "bottom_ad_slot": "9081726354",
                "custom_header_banner_url": "",
                "custom_header_link": "https://epaper." + t_data["slug"] + ".com",
            },
            status="active",
        )
        db.add(tenant)
        await db.flush()

        # Create Tenant Admin User
        t_admin = TenantUser(
            tenant_id=tenant.id,
            email=t_data["admin_email"],
            full_name=f"{tenant.name} Chief Editor",
            hashed_password=get_password_hash("Admin@123"),
            role="TENANT_ADMIN",
            is_active=True,
        )
        db.add(t_admin)

        created_editions = []
        for idx, (ed_name, ed_slug) in enumerate(t_data["editions"], start=1):
            ed = Edition(
                tenant_id=tenant.id,
                name=ed_name,
                slug=ed_slug,
                display_order=idx,
                is_active=True,
            )
            db.add(ed)
            created_editions.append(ed)
        await db.flush()

        # Render full DeepZoom issues for the primary edition (Today + Yesterday for Archive Calendar)
        primary_ed = created_editions[0]
        for day_offset in [0, 1]:
            issue_date = today - timedelta(days=day_offset)
            pdf_bytes = generate_sample_newspaper_pdf_bytes(
                newspaper_name=tenant.name,
                edition_name=primary_ed.name,
                primary_hex=tenant.brand_primary_color,
                pub_date=issue_date,
                num_pages=4,
            )
            pdf_key = build_issue_pdf_key(
                pub_date=issue_date,
                edition_slug=primary_ed.slug,
                revision=1,
                tenant_id=tenant.id,
            )
            await storage_service.save_asset(
                storage_key=pdf_key,
                data=pdf_bytes,
                asset_type="ISSUE_PDF",
                mime_type="application/pdf",
                original_filename=f"{tenant.slug}_{issue_date.isoformat()}.pdf",
                db_session=db,
                tenant_id=tenant.id,
            )

            issue = Issue(
                tenant_id=tenant.id,
                edition_id=primary_ed.id,
                publication_date=issue_date,
                revision=1,
                page_count=4,
                pdf_storage_key=pdf_key,
                pdf_file_size=len(pdf_bytes),
                status="PROCESSING",
                views_count=145 if day_offset == 0 else 88,
            )
            db.add(issue)
            await db.flush()

            pages = await pdf_processor.process_issue_pdf(
                pdf_bytes=pdf_bytes,
                issue=issue,
                edition_slug=primary_ed.slug,
                db_session=db,
            )
            issue.processing_progress = 100
            issue.processing_message = "Published & DeepZoom Tiles Ready"

            # Add clickable smart article regions on Page 1
            if pages:
                p1 = pages[0]
                regions = [
                    ArticleRegion(
                        tenant_id=tenant.id,
                        issue_id=issue.id,
                        page_id=p1.id,
                        title=f"{tenant.name} Launches Next-Gen Ultra-Sharp DeepZoom Digital E-Paper Platform",
                        coordinates={"x": 0.045, "y": 0.16, "width": 0.91, "height": 0.32},
                        content_text=(
                            f"Readers across the globe can now experience zero-blur 300 DPI vector typography, "
                            f"instant 512x512 WebP pyramid tile streaming, and 1-click branded WhatsApp article clipping "
                            f"on {tenant.name} ({primary_ed.name})."
                        ),
                    ),
                    ArticleRegion(
                        tenant_id=tenant.id,
                        issue_id=issue.id,
                        page_id=p1.id,
                        title="High-Speed Metro Rail & Smart Infrastructure Corridor Receives ₹18,500 Crore Approval",
                        coordinates={"x": 0.045, "y": 0.50, "width": 0.44, "height": 0.43},
                        content_text=(
                            "The cabinet cleared phase-III expansion connecting major IT hubs, industrial parks, "
                            "and regional transit terminals with sustainable solar-powered stations."
                        ),
                    ),
                    ArticleRegion(
                        tenant_id=tenant.id,
                        issue_id=issue.id,
                        page_id=p1.id,
                        title="Record Monsoon Harvest Boosts Agricultural Exports by 24% Across Southern States",
                        coordinates={"x": 0.51, "y": 0.50, "width": 0.44, "height": 0.43},
                        content_text=(
                            "Modernized cold-chain logistics and direct digital procurement portals have enabled farmers "
                            "to secure premium prices in international markets this quarter."
                        ),
                    ),
                ]
                for reg in regions:
                    db.add(reg)

    # Also seed the Fleet Manager & physical `deployed_clients/<slug>/` folders
    from app.models.fleet import DeployedInstance
    from app.core.provisioner import client_provisioner

    fleet_seed = [
        {
            "client_name": "Disha Daily",
            "client_slug": "dishadaily",
            "domain": "epaper.dishadaily.com",
            "brand_primary_color": "#dc2626",
            "brand_secondary_color": "#0f172a",
            "editions": ["Hyderabad Main", "Warangal Edition", "Vijayawada Edition"],
            "admin_email": "editor@dishadaily.com",
            "admin_password": "Admin@123",
            "deployment_mode": "LOCAL_VPS",
            "plan_name": "Standard Shared VPS (Docker Folder)",
            "monthly_price_inr": 6500,
            "assigned_port": 8101,
            "vps_provider": "Our Primary Shared VPS",
            "vps_ip": "127.0.0.1",
            "vps_root_password": None,
        },
        {
            "client_name": "Praja Jyothi",
            "client_slug": "prajajyothi",
            "domain": "epaper.prajajyothi.com",
            "brand_primary_color": "#034ea2",
            "brand_secondary_color": "#1e293b",
            "editions": ["State Main Edition", "Greater Hyderabad", "Visakhapatnam", "Tirupati", "Warangal", "Khammam"],
            "admin_email": "editor@prajajyothi.com",
            "admin_password": "Admin@123",
            "deployment_mode": "REMOTE_DEDICATED_VPS",
            "plan_name": "Enterprise Multi-Edition Dedicated VPS",
            "monthly_price_inr": 18500,
            "assigned_port": 8102,
            "vps_provider": "Hetzner Cloud Dedicated (8 vCPU / 32GB RAM)",
            "vps_ip": "65.108.142.88",
            "vps_root_password": "RootVps#Praja2026!Secret",
        },
        {
            "client_name": "City Herald",
            "client_slug": "cityherald",
            "domain": "epaper.cityherald.com",
            "brand_primary_color": "#059669",
            "brand_secondary_color": "#064e3b",
            "editions": ["Metro Financial", "National Edition"],
            "admin_email": "editor@cityherald.com",
            "admin_password": "Admin@123",
            "deployment_mode": "LOCAL_VPS",
            "plan_name": "Standard Shared VPS (Docker Folder)",
            "monthly_price_inr": 5000,
            "assigned_port": 8103,
            "vps_provider": "Our Primary Shared VPS",
            "vps_ip": "127.0.0.1",
            "vps_root_password": None,
        },
    ]

    for f_item in fleet_seed:
        folder_path, logs = client_provisioner.build_client_instance_folder(
            client_name=f_item["client_name"],
            client_slug=f_item["client_slug"],
            domain=f_item["domain"],
            brand_primary_color=f_item["brand_primary_color"],
            brand_secondary_color=f_item["brand_secondary_color"],
            editions_list=f_item["editions"],
            admin_email=f_item["admin_email"],
            admin_password=f_item["admin_password"],
            assigned_port=f_item["assigned_port"],
            deployment_mode=f_item["deployment_mode"],
            vps_ip=f_item["vps_ip"],
        )
        db.add(
            DeployedInstance(
                client_name=f_item["client_name"],
                client_slug=f_item["client_slug"],
                domain=f_item["domain"],
                brand_primary_color=f_item["brand_primary_color"],
                brand_secondary_color=f_item["brand_secondary_color"],
                editions_list=f_item["editions"],
                admin_email=f_item["admin_email"],
                admin_password_plain=f_item["admin_password"],
                deployment_mode=f_item["deployment_mode"],
                plan_name=f_item["plan_name"],
                monthly_price_inr=f_item["monthly_price_inr"],
                local_folder_path=folder_path,
                assigned_port=f_item["assigned_port"],
                vps_provider=f_item["vps_provider"],
                vps_ip=f_item["vps_ip"],
                vps_ssh_port=22,
                vps_ssh_user="root",
                vps_root_password=f_item["vps_root_password"],
                remote_deploy_path="/opt/epaper",
                status="REMOTE_VPS_PACKAGE_READY" if f_item["deployment_mode"] == "REMOTE_DEDICATED_VPS" else "RUNNING_LOCAL_VPS",
                provision_logs=logs,
            )
        )

    await db.commit()
    print("✅ Multi-Tenant & VPS Fleet Seed Complete: Disha Daily, Praja Jyothi, and City Herald folders generated!")
