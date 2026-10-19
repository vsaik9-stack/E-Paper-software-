import io
import os
from datetime import datetime
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


def hex_to_rgb(hex_color: str, fallback: Tuple[int, int, int] = (220, 38, 38)) -> Tuple[int, int, int]:
    """Convert hex color string (#dc2626) to RGB tuple."""
    try:
        h = hex_color.lstrip("#")
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        if len(h) == 3:
            return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16))
    except Exception:
        pass
    return fallback


class ClipGenerator:
    """
    Composites high-DPI newspaper vector crops with dynamic White-Label Tenant masthead logo/name,
    centered publication date & edition title, and clean clipping border matching classic newspaper CMS layouts.
    """

    def __init__(self):
        self.logo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "jyothi_logo_clean.png"
        )

    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Load clean readable sans-serif font for Linux & macOS."""
        candidate_paths = [
            # Linux paths
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            # macOS paths
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        try:
            return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
        except Exception:
            pass
        return ImageFont.load_default()

    def create_branded_clip(
        self,
        crop_image_bytes: bytes,
        edition_name: str = "Main Edition",
        pub_date: str = "",
        page_number: int = 1,
        headline: Optional[str] = None,
        tenant_name: str = "Disha Daily",
        tenant_primary_color: str = "#dc2626",
        tenant_secondary_color: str = "#1e293b",
        tenant_copyright: Optional[str] = None,
        tenant_logo_bytes: Optional[bytes] = None,
    ) -> bytes:
        """
        Generates a White-Label branded newspaper clipping with:
        - Left side: Tenant Official Logo (or stylized Masthead Banner in Tenant Brand Color)
        - Right side: Publication date, Edition name & Page number with crisp brand badges
        - Clean divider line, vector clipping frame, and tenant copyright footer
        """
        crop_img = Image.open(io.BytesIO(crop_image_bytes))
        if crop_img.mode in ("RGBA", "P"):
            crop_img = crop_img.convert("RGB")

        cw, ch = crop_img.size

        primary_rgb = hex_to_rgb(tenant_primary_color, (220, 38, 38))
        secondary_rgb = hex_to_rgb(tenant_secondary_color, (30, 41, 59))

        # Format date like "19-Oct-2026"
        formatted_date = pub_date
        try:
            for fmt in ("%Y-%m-%d", "%d %B %Y", "%d-%m-%Y", "%d %b %Y"):
                try:
                    dt = datetime.strptime(pub_date, fmt)
                    formatted_date = dt.strftime("%d-%b-%Y")
                    break
                except ValueError:
                    pass
        except Exception:
            pass

        logo_img = None
        if tenant_logo_bytes:
            try:
                logo_img = Image.open(io.BytesIO(tenant_logo_bytes)).convert("RGBA")
            except Exception:
                logo_img = None
        elif os.path.exists(self.logo_path) and "jyothi" in tenant_name.lower():
            try:
                logo_img = Image.open(self.logo_path).convert("RGBA")
            except Exception:
                logo_img = None

        logo_target_w = max(140, int(cw * 0.32))

        if logo_img:
            logo_scale = logo_target_w / logo_img.width
            logo_target_h = int(logo_img.height * logo_scale)
            resized_logo = logo_img.resize((logo_target_w, logo_target_h), Image.Resampling.BILINEAR)
        else:
            logo_target_h = int(logo_target_w * 0.30)
            resized_logo = None

        # Proportional font sizes strictly tied to crop width
        date_font_size = max(16, int(cw * 0.032))
        edition_font_size = max(14, int(cw * 0.026))
        page_font_size = max(14, int(cw * 0.026))
        footer_font_size = max(12, int(cw * 0.020))

        date_font = self._get_font(date_font_size, bold=True)
        edition_font = self._get_font(edition_font_size, bold=True)
        page_font = self._get_font(page_font_size, bold=True)
        footer_font = self._get_font(footer_font_size, bold=False)

        # Proportional Spacing
        padding_x = max(14, int(cw * 0.035))
        padding_y = max(12, int(cw * 0.024))
        line_gap = max(4, int(cw * 0.008))

        total_text_h = date_font_size + edition_font_size + page_font_size + (line_gap * 2)
        content_h = max(logo_target_h, total_text_h)
        header_h = padding_y * 2 + content_h

        footer_h = max(24, int(cw * 0.038))

        total_w = cw
        total_h = header_h + ch + footer_h

        composite = Image.new("RGB", (total_w, total_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(composite)

        # Top brand accent bar
        accent_h = max(4, int(cw * 0.006))
        draw.rectangle([(0, 0), (total_w, accent_h)], fill=primary_rgb)

        # 1. Left Side: Official Tenant Logo or Branded Masthead
        logo_x = padding_x
        logo_y = padding_y + (content_h - logo_target_h) // 2

        if resized_logo:
            composite.paste(resized_logo, (logo_x, logo_y), resized_logo)
        else:
            masthead_font = self._get_font(max(22, int(date_font_size * 1.55)), bold=True)
            sub_font = self._get_font(max(11, int(edition_font_size * 0.75)), bold=True)
            draw.text(
                (logo_x, logo_y + int(logo_target_h * 0.38)),
                tenant_name.upper(),
                fill=primary_rgb,
                font=masthead_font,
                anchor="lm",
            )
            draw.text(
                (logo_x, logo_y + int(logo_target_h * 0.82)),
                "DIGITAL E-PAPER EDITION",
                fill=secondary_rgb,
                font=sub_font,
                anchor="lm",
            )

        # 2. Right Side: Publication Date, Edition Name, Page Number
        right_x = total_w - padding_x
        text_start_y = padding_y + (content_h - total_text_h) // 2

        date_y = text_start_y
        edition_y = date_y + date_font_size + line_gap
        page_y = edition_y + edition_font_size + line_gap

        # Date
        draw.text((right_x, date_y), formatted_date, fill=secondary_rgb, font=date_font, anchor="ra")

        # Edition Name
        clean_edition = edition_name.strip() if edition_name else tenant_name
        draw.text((right_x, edition_y), clean_edition, fill=(51, 65, 85), font=edition_font, anchor="ra")

        # Page Number (Tenant Brand Primary Color)
        page_text = f"Page {page_number}"
        draw.text((right_x, page_y), page_text, fill=primary_rgb, font=page_font, anchor="ra")

        # 3. Header Bottom Clean Divider Line
        border_w = max(2, int(cw * 0.002))
        draw.line([(0, header_h - 1), (total_w, header_h - 1)], fill=(226, 232, 240), width=border_w)

        # 4. Paste Vector Crop Image
        composite.paste(crop_img, (0, header_h))

        # 5. Bottom Copyright & Digital Edition Footer Strip
        footer_top_y = header_h + ch
        draw.line([(0, footer_top_y), (total_w, footer_top_y)], fill=(226, 232, 240), width=border_w)

        footer_str = tenant_copyright or f"© {tenant_name} Digital E-Paper • Clipped & Shared via {tenant_name}"
        footer_text_y = footer_top_y + (footer_h // 2)
        draw.text((padding_x, footer_text_y), footer_str, fill=(100, 116, 139), font=footer_font, anchor="lm")

        # 6. Outer Frame Border
        draw.rectangle([(0, 0), (total_w - 1, total_h - 1)], outline=(203, 213, 225), width=border_w)

        output = io.BytesIO()
        composite.save(output, format="JPEG", quality=88, optimize=True, subsampling=1)
        return output.getvalue()


clip_generator = ClipGenerator()
