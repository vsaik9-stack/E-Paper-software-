"use client";

import React, { useEffect, useRef } from "react";
import OpenSeadragon from "openseadragon";

export interface RenderedPageBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface OSDViewerProps {
  imageUrl: string;
  dziUrl?: string | null;
  mappedArticles: any[];
  onArticleClick: (article: any) => void;
  zoomLevel: number;
  onZoomChange: (zoomLevel: number) => void;
  onZoomReset: () => void;
  turnDirection?: "next" | "prev" | null;
  onPageBoundsChange?: (bounds: RenderedPageBounds | null) => void;
  isCropMode?: boolean;
}

export function OSDViewer({
  imageUrl,
  dziUrl,
  mappedArticles,
  onArticleClick,
  zoomLevel,
  onZoomChange,
  onZoomReset,
  onPageBoundsChange,
  isCropMode = false,
}: OSDViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const osdRef = useRef<OpenSeadragon.Viewer | null>(null);
  const isInitializedRef = useRef<boolean>(false);

  // Initialize OSD Once on Mount
  useEffect(() => {
    if (!viewerRef.current || isInitializedRef.current) return;

    const initialSource = dziUrl || {
      type: "image",
      url: imageUrl,
    };

    const viewer = OpenSeadragon({
      element: viewerRef.current,
      prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/3.0.0/images/",
      tileSources: initialSource as any,
      animationTime: 0.1,
      blendTime: 0.0,
      constrainDuringPan: true,
      maxZoomPixelRatio: 4.0,
      minZoomImageRatio: 0.9,
      visibilityRatio: 1,
      imageLoaderLimit: 8,
      showNavigationControl: false,
      gestureSettingsMouse: {
        clickToZoom: false,
        dblClickToZoom: false,
      },
      gestureSettingsTouch: {
        clickToZoom: false,
        dblClickToZoom: false,
        pinchToZoom: true,
      },
    });

    osdRef.current = viewer;
    isInitializedRef.current = true;

    return () => {
      viewer.destroy();
      osdRef.current = null;
      isInitializedRef.current = false;
    };
  }, []);

  // Seamlessly swap image or DZI on page changes
  useEffect(() => {
    const viewer = osdRef.current;
    if (!viewer || !isInitializedRef.current) return;
    if (!dziUrl && !imageUrl) return;

    const source = dziUrl || {
      type: "image",
      url: imageUrl,
    };

    viewer.open(source as any);
  }, [dziUrl, imageUrl]);

  // Hook into viewport events (fit home, zoom, and exact page pixel bounds)
  useEffect(() => {
    const viewer = osdRef.current;
    if (!viewer) return;

    const fitMobileOrHome = () => {
      if (typeof window !== "undefined" && window.innerWidth < 768) {
        viewer.viewport.fitHorizontally(true);
        const bounds = viewer.viewport.getBounds();
        viewer.viewport.panTo(new OpenSeadragon.Point(bounds.getCenter().x, bounds.height / 2), true);
      } else {
        viewer.viewport.goHome(true);
      }
    };

    const publishPageBounds = () => {
      if (!onPageBoundsChange || viewer.world.getItemCount() === 0) return;
      const item = viewer.world.getItemAt(0);
      if (!item) return;
      const b = item.getBounds(true);
      const p0 = viewer.viewport.pixelFromPoint(new OpenSeadragon.Point(b.x, b.y), true);
      const p1 = viewer.viewport.pixelFromPoint(new OpenSeadragon.Point(b.x + b.width, b.y + b.height), true);
      const w = p1.x - p0.x;
      const h = p1.y - p0.y;
      if (w > 10 && h > 10) {
        onPageBoundsChange({
          left: Math.round(p0.x),
          top: Math.round(p0.y),
          width: Math.round(w),
          height: Math.round(h),
        });
      }
    };

    let lastReportedZoom = 1.0;
    const publishZoom = () => {
      const homeZoom = viewer.viewport.getHomeZoom();
      const currentZoom = viewer.viewport.getZoom();
      const normalizedZoom = homeZoom > 0 ? Number((currentZoom / homeZoom).toFixed(2)) : 1;
      if (Math.abs(normalizedZoom - lastReportedZoom) >= 0.05) {
        lastReportedZoom = normalizedZoom;
        onZoomChange(normalizedZoom);
      }
      if (isCropMode) publishPageBounds();
    };

    const onOpen = () => {
      fitMobileOrHome();
      publishZoom();
      publishPageBounds();

      // Ensure canvas uses highest quality filtering for crystal-clear Telugu typography
      try {
        const canvas = viewerRef.current?.querySelector("canvas");
        if (canvas) {
          canvas.style.imageRendering = "-webkit-optimize-contrast";
          const ctx = canvas.getContext("2d");
          if (ctx) {
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = "high";
          }
        }
      } catch {}
    };

    viewer.addHandler("open", onOpen);
    viewer.addHandler("zoom", publishZoom);
    if (isCropMode) {
      publishPageBounds();
      requestAnimationFrame(publishPageBounds);
      setTimeout(publishPageBounds, 50);

      viewer.addHandler("pan", publishPageBounds);
      viewer.addHandler("animation", publishPageBounds);
      viewer.addHandler("resize", publishPageBounds);
    }

    return () => {
      viewer.removeHandler("open", onOpen);
      viewer.removeHandler("zoom", publishZoom);
      viewer.removeHandler("pan", publishPageBounds);
      viewer.removeHandler("animation", publishPageBounds);
      viewer.removeHandler("resize", publishPageBounds);
    };
  }, [onZoomChange, onPageBoundsChange, isCropMode]);

  // Sync zoom level from parent
  useEffect(() => {
    const viewer = osdRef.current;
    if (!viewer || viewer.world.getItemCount() === 0) return;

    const homeZoom = viewer.viewport.getHomeZoom();
    if (zoomLevel <= 1) {
      viewer.viewport.goHome(true);
      return;
    }

    const target = homeZoom * zoomLevel;
    const current = viewer.viewport.getZoom();
    if (Math.abs(current - target) > 0.02) {
      viewer.viewport.zoomTo(target);
    }
  }, [zoomLevel]);

  // Render clickable mapped article overlays
  useEffect(() => {
    const viewer = osdRef.current;
    if (!viewer) return;

    const overlayTrackers: OpenSeadragon.MouseTracker[] = [];

    const applyOverlays = () => {
      if (viewer.world.getItemCount() === 0) return;
      viewer.clearOverlays();

      const item = viewer.world.getItemAt(0);
      if (!item) return;
      const imageBounds = item.getBounds();

      mappedArticles.forEach((art) => {
        const b = art.bounds;
        if (!b) return;

        const overlayEle = document.createElement("button");
        overlayEle.className =
          "cursor-pointer rounded transition duration-150 z-30 absolute border border-transparent bg-transparent opacity-0 focus:opacity-100 hover:opacity-100 active:opacity-100 focus:border-red-500 hover:border-red-500/70 focus:bg-red-500/12 hover:bg-red-500/10 active:bg-red-500/16";
        overlayEle.type = "button";
        overlayEle.title = art.headline || "View Article";
        overlayEle.setAttribute("aria-label", art.headline || "Open article");

        overlayEle.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          onArticleClick(art);
        });

        const tracker = new OpenSeadragon.MouseTracker({
          element: overlayEle,
          clickHandler: (event) => {
            (event as any).preventDefaultAction = true;
            onArticleClick(art);
          },
          pressHandler: (event) => {
            (event as any).preventDefaultAction = true;
          },
        });
        overlayTrackers.push(tracker);

        const rect = new OpenSeadragon.Rect(b.x, b.y * imageBounds.height, b.width, b.height * imageBounds.height);
        viewer.addOverlay({
          element: overlayEle,
          location: rect,
        });
      });
    };

    if (viewer.world.getItemCount() > 0) {
      applyOverlays();
    } else {
      viewer.addOnceHandler("open", applyOverlays);
    }

    return () => {
      overlayTrackers.forEach((t) => t.destroy());
    };
  }, [mappedArticles, onArticleClick]);

  return (
    <div
      ref={viewerRef}
      className="w-full h-full relative bg-white object-contain shadow-2xl touch-none select-none overscroll-none"
      style={{ touchAction: "none", overscrollBehavior: "none" }}
    />
  );
}
