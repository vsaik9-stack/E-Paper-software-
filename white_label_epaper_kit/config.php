<?php
/**
 * ============================================================================
 * WHITE-LABEL E-PAPER CMS CONFIGURATION
 * Stress Busters Digital Media Engine
 * ============================================================================
 * Edit only the values below for any new client / newspaper!
 * Everything else runs automatically.
 */

return [
    // Client Brand Identity
    'newspaper_name'     => 'Your Newspaper Name',
    'newspaper_tagline'  => 'Your Newspaper Tagline • Daily Broadsheet',
    'main_website_url'   => 'https://example.com',
    'logo_path'          => 'assets/logo.png', // Place the client's PNG/WebP logo in assets/

    // Brand Colors
    'primary_color'      => '#dc2626', // Brand accent color (buttons, borders, pills)
    'secondary_color'    => '#0f172a', // Dark theme bars / slate accents

    // Default Editions
    'editions' => [
        ['name' => 'Main Edition', 'slug' => 'main', 'order' => 1],
        ['name' => 'State Edition', 'slug' => 'state', 'order' => 2],
        ['name' => 'District Edition', 'slug' => 'district', 'order' => 3],
    ],

    // Google AdSense (Leave empty string '' if client doesn't use ads)
    'adsense_client_id'  => '', // e.g., 'ca-pub-1059950253311579'
    'adsense_slot_id'    => '', // e.g., '7406203456'

    // Admin Panel Credentials
    'admin_username'     => 'admin',
    'admin_email'        => 'editor@example.com',
    'admin_password'     => 'Admin@2026', // Change before launching!

    // Developer / Agency Branding (Stress Busters Digital Media)
    'agency' => [
        'name'        => 'Stress Busters Digital Media',
        'website'     => 'https://stressbusters.co.in',
        'logo_path'   => 'assets/stressbusters-logo.png',
        'show_badge'  => true,
    ],
];
