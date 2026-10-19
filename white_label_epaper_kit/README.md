# White-Label E-Paper Deployment Kit
### Developed & Powered by Stress Busters Digital Media

This directory contains the complete, production-tested White-Label E-Paper portal with:
- **60fps Jyothi E-Paper Cropping Engine** (Zero-latency touch capture, 3×3 rule-of-thirds grid, auto-flipping toolbar).
- **Date-First Newsstand & Full-Screen Broadsheet Reader** with numbered pagination.
- **WhatsApp Article Sharing with Official Newspaper Masthead Branded Clipping**.
- **Admin Dashboard** for instant drag-and-drop daily PDF publishing.
- **Google AdSense ready** & **Stress Busters Digital Media branding**.
- **100% self-contained SQLite3 + PHP Imagick engine** — zero complex MySQL setup, zero Redis or Node.js required. Runs on any shared hosting (Hostinger, cPanel, Plesk) or VPS (Ubuntu/Nginx/Apache).

---

## Quick 3-Step Setup for a New Client / Newspaper

### Step 1: Add Client Logo & Edit 1 File
1. Replace `assets/logo.png` with the client's transparent newspaper masthead logo.
2. Open [`config.php`](config.php) and update:
   ```php
   'newspaper_name'     => 'Your Client Newspaper',
   'newspaper_tagline'  => 'Official Telugu Daily',
   'main_website_url'   => 'https://clientnews.com',
   'primary_color'      => '#dc2626', // Client brand color
   'admin_password'     => 'ClientSecurePassword@2026',
   ```

### Step 2: Point Domain (DNS)
In the client's DNS manager (GoDaddy, Cloudflare, Hostinger, Namecheap):
- **Option A (Subdomain like `epaper.client.com`)**:
  - Add a **CNAME** record: `epaper` $\rightarrow$ pointing to your server domain (or Hostinger subdomain).
  - *OR* add an **A** record: `epaper` $\rightarrow$ pointing to your server's IP address (`195.179.239.146` or your VPS IP).
- **Option B (Subfolder like `client.com/epaper/`)**:
  - Simply upload this folder into `public_html/epaper/`.

### Step 3: Upload & Deploy
- **On Shared Hosting (Hostinger / cPanel)**:
  - Upload the contents of this folder into `public_html/` (for subdomain) or `public_html/epaper/`.
  - Ensure PHP 8.0+ is active and `extension=imagick` + `extension=sqlite3` (enabled by default on Hostinger).
- **On Ubuntu VPS (Nginx / Apache)**:
  - Copy folder to `/var/www/epaper`
  - Run:
    ```bash
    sudo chown -R www-data:www-data /var/www/epaper
    sudo chmod -R 775 /var/www/epaper/storage
    ```

---

## Daily Operation & Admin Portal
- **Admin URL**: `https://epaper.clientdomain.com/admin/`
- **Default Login**: Email configured in `config.php`
- **Uploading New Papers**:
  - Drag and drop today's broadsheet PDF, pick the date and edition, click **Publish**.
  - The engine automatically renders high-resolution WebP pages, broadsheet thumbnails, and generates WhatsApp-shareable branded clippings in seconds.
