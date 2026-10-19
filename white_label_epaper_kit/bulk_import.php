<?php
/**
 * Complete Historical Archive Importer for Vibhare Telugu Daily E-Paper (2021 - 2026)
 * Scans:
 * 1. /tmp/vibhare_new_oct (latest October 2026 PDFs)
 * 2. All folders inside domains/vibharenews.com/public_html/wp-content/uploads/ (2021, 2022, 2023, 2024, 2025, 2026)
 * Parses all filename formats (DD-MM.-YYYY, DD.MM.YY, DD-MM.YYV, etc.) and imports newest first.
 */

error_reporting(E_ALL & ~E_DEPRECATED & ~E_NOTICE);
ini_set('memory_limit', '512M');
ini_set('max_execution_time', '0');

$BASE_DIR = __DIR__; // domains/vibharenews.com/public_html/epaper
$STORAGE_DIR = $BASE_DIR . '/storage';
$DB_FILE = $STORAGE_DIR . '/vibhare_epaper.sqlite';

// Load functions from api/index.php without triggering HTTP routes
$apiCode = file_get_contents(__DIR__ . '/api/index.php');
$cutPos = strpos($apiCode, '$pdo = get_db();');
if ($cutPos !== false) {
    $funcsOnly = substr($apiCode, 5, $cutPos - 5);
    $funcsOnly = str_replace('$BASE_DIR = dirname(__DIR__);', '$BASE_DIR = __DIR__;', $funcsOnly);
    eval($funcsOnly);
} else {
    die("Could not parse api/index.php\n");
}

$pdo = get_db();

$ed = $pdo->query("SELECT * FROM editions WHERE slug = 'main' LIMIT 1")->fetch();
if (!$ed) {
    $ed = $pdo->query("SELECT * FROM editions ORDER BY id ASC LIMIT 1")->fetch();
}
$editionId = (int)$ed['id'];
$editionSlug = $ed['slug'];

function parse_date_from_filename(string $filepath): ?string {
    $base = basename($filepath);
    // Match DD [.-_ ]+ MM [.-_ ]+ (20YY or YY) even if followed immediately by V/v/-
    if (preg_match('/(\d{1,2})[.\-_ ]+(\d{1,2})[.\-_ ]+(20\d{2}|\d{2})(?:[^0-9]|$)/', $base, $m)) {
        $day = (int)$m[1];
        $month = (int)$m[2];
        $year = (int)$m[3];
        if ($year < 100) {
            $year += 2000;
        }
        if ($year >= 2020 && $year <= 2027 && checkdate($month, $day, $year)) {
            return sprintf('%04d-%02d-%02d', $year, $month, $day);
        }
    }
    return null;
}

$pdfFiles = [];

// Source 1: Uploaded local folder PDFs (/tmp/vibhare_new_oct)
$localUploadDir = '/tmp/vibhare_new_oct';
if (is_dir($localUploadDir)) {
    foreach (glob($localUploadDir . '/*.pdf') as $f) {
        $pdfFiles[] = $f;
    }
}

// Source 2: All WordPress Media Library PDFs (2021 - 2026)
$wpUploadsRoot = dirname($BASE_DIR) . '/wp-content/uploads';
if (is_dir($wpUploadsRoot)) {
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($wpUploadsRoot));
    foreach ($it as $file) {
        if ($file->isFile() && strtolower($file->getExtension()) === 'pdf') {
            $pdfFiles[] = $file->getPathname();
        }
    }
}

$byDate = [];
foreach ($pdfFiles as $path) {
    $dt = parse_date_from_filename($path);
    if ($dt) {
        if (!isset($byDate[$dt])) {
            $byDate[$dt] = $path;
        }
    }
}

krsort($byDate); // Newest date first!

echo "Total unique dated PDFs discovered (2021-2026): " . count($byDate) . "\n";

$imported = 0;
$skipped = 0;

foreach ($byDate as $pubDate => $pdfPath) {
    $chk = $pdo->prepare("SELECT id, page_count FROM issues WHERE publication_date = ? AND edition_id = ? LIMIT 1");
    $chk->execute([$pubDate, $editionId]);
    $existing = $chk->fetch();
    if ($existing && (int)$existing['page_count'] > 0) {
        $skipped++;
        continue;
    }

    echo "[IMPORTING] $pubDate from " . basename($pdfPath) . " ... ";
    $t0 = microtime(true);
    try {
        $res = process_pdf_into_issue($pdo, $pdfPath, $editionId, $pubDate, $editionSlug);
        $elapsed = round(microtime(true) - $t0, 2);
        echo "OK ({$res['page_count']} pages in {$elapsed}s, Issue #{$res['issue_id']})\n";
        $imported++;
    } catch (Exception $e) {
        echo "ERROR: " . $e->getMessage() . "\n";
    }
}

echo "\n========================================\n";
echo "Import Complete! Imported: $imported | Skipped (already present): $skipped\n";
echo "========================================\n";
