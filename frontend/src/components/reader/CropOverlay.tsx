"use client";

import React, { useRef, useState } from "react";
import { Share2, X } from "lucide-react";
import { RenderedPageBounds } from "./OSDViewer";

export interface CropBox {
  x: number; // 0.0 to 1.0 (relative to newspaper page)
  y: number; // 0.0 to 1.0 (relative to newspaper page)
  width: number;
  height: number;
}

interface CropOverlayProps {
  pageBounds?: RenderedPageBounds | null;
  onCropComplete: (box: CropBox) => void;
  onCancel: () => void;
}

type DragType = "move" | "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

export function CropOverlay({ pageBounds, onCropComplete, onCancel }: CropOverlayProps) {
  const pageContainerRef = useRef<HTMLDivElement>(null);

  // Normalized coordinates from 0.0 to 1.0 strictly relative to the newspaper page image
  const [box, setBox] = useState<CropBox>({
    x: 0.08,
    y: 0.22,
    width: 0.84,
    height: 0.45,
  });

  const dragRef = useRef<{
    type: DragType;
    startX: number;
    startY: number;
    startBox: CropBox;
    containerWidth: number;
    containerHeight: number;
  } | null>(null);

  const startDrag = (e: React.PointerEvent, type: DragType) => {
    e.preventDefault();
    e.stopPropagation();

    if (!pageContainerRef.current) return;
    const rect = pageContainerRef.current.getBoundingClientRect();

    dragRef.current = {
      type,
      startX: e.clientX,
      startY: e.clientY,
      startBox: { ...box },
      containerWidth: Math.max(10, rect.width),
      containerHeight: Math.max(10, rect.height),
    };

    const handlePointerMove = (moveEvent: PointerEvent) => {
      if (!dragRef.current) return;
      moveEvent.preventDefault();
      moveEvent.stopPropagation();

      const { type, startX, startY, startBox, containerWidth, containerHeight } = dragRef.current;

      const deltaNormX = (moveEvent.clientX - startX) / containerWidth;
      const deltaNormY = (moveEvent.clientY - startY) / containerHeight;

      const MIN_SIZE = 0.04;

      let newX = startBox.x;
      let newY = startBox.y;
      let newW = startBox.width;
      let newH = startBox.height;

      if (type === "move") {
        newX = Math.max(0, Math.min(1.0 - startBox.width, startBox.x + deltaNormX));
        newY = Math.max(0, Math.min(1.0 - startBox.height, startBox.y + deltaNormY));
      } else {
        // Horizontal resizing
        if (type.includes("w")) {
          const potentialW = startBox.width - deltaNormX;
          if (potentialW >= MIN_SIZE && startBox.x + deltaNormX >= 0) {
            newX = startBox.x + deltaNormX;
            newW = potentialW;
          }
        } else if (type.includes("e")) {
          const potentialW = startBox.width + deltaNormX;
          if (potentialW >= MIN_SIZE && startBox.x + potentialW <= 1.0) {
            newW = potentialW;
          }
        }

        // Vertical resizing
        if (type.includes("n")) {
          const potentialH = startBox.height - deltaNormY;
          if (potentialH >= MIN_SIZE && startBox.y + deltaNormY >= 0) {
            newY = startBox.y + deltaNormY;
            newH = potentialH;
          }
        } else if (type.includes("s")) {
          const potentialH = startBox.height + deltaNormY;
          if (potentialH >= MIN_SIZE && startBox.y + potentialH <= 1.0) {
            newH = potentialH;
          }
        }
      }

      setBox({
        x: Math.max(0, Math.min(1.0 - newW, newX)),
        y: Math.max(0, Math.min(1.0 - newH, newY)),
        width: Math.max(MIN_SIZE, Math.min(1.0, newW)),
        height: Math.max(MIN_SIZE, Math.min(1.0, newH)),
      });
    };

    const handlePointerUp = (upEvent: PointerEvent) => {
      upEvent.preventDefault();
      upEvent.stopPropagation();
      dragRef.current = null;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: false });
    window.addEventListener("pointerup", handlePointerUp, { passive: false });
    window.addEventListener("pointercancel", handlePointerUp, { passive: false });
  };

  if (!pageBounds || pageBounds.width <= 10 || pageBounds.height <= 10) {
    return null;
  }

  const isTopClose = box.y < 0.08;

  const containerStyle: React.CSSProperties = {
    position: "absolute",
    left: `${pageBounds.left}px`,
    top: `${pageBounds.top}px`,
    width: `${pageBounds.width}px`,
    height: `${pageBounds.height}px`,
  };

  return (
    <div
      className="absolute inset-0 z-50 pointer-events-none select-none touch-none overscroll-none overflow-hidden"
      style={{ touchAction: "none" }}
    >
      {/* Newspaper Page Aligned Coordinate Space */}
      <div
        ref={pageContainerRef}
        style={containerStyle}
        className="pointer-events-none relative"
      >
        {/* Interactive Crop Box */}
        <div
          style={{
            position: "absolute",
            left: `${box.x * 100}%`,
            top: `${box.y * 100}%`,
            width: `${box.width * 100}%`,
            height: `${box.height * 100}%`,
          }}
          onPointerDown={(e) => startDrag(e, "move")}
          className="pointer-events-auto cursor-move border-2 border-[#0099ff] bg-[#0099ff]/15 shadow-[0_0_0_9999px_rgba(0,0,0,0.65)] touch-none select-none relative"
        >
          {/* Floating Action Buttons (Simple, User-Friendly English) */}
          <div
            className={`absolute ${
              isTopClose ? "top-2 left-2" : "-top-12 left-0"
            } flex items-center shadow-2xl rounded-xl overflow-hidden z-50 select-none border border-slate-700/80 bg-slate-900 pointer-events-auto gap-0.5 p-0.5`}
            onPointerDown={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCropComplete(box);
              }}
              className="bg-[#25D366] hover:bg-[#1EBE5D] active:bg-[#1DA851] text-white px-3.5 py-2 font-bold text-xs sm:text-sm flex items-center gap-1.5 transition rounded-lg cursor-pointer shadow-md"
              title="Crop and Share Article"
            >
              <Share2 className="w-4 h-4 text-white" />
              <span>Crop & Share</span>
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onCancel();
              }}
              className="bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-200 px-3 py-2 font-bold text-xs sm:text-sm flex items-center gap-1 transition rounded-lg cursor-pointer"
              title="Cancel"
            >
              <X className="w-4 h-4 text-slate-300" />
              <span>Cancel</span>
            </button>
          </div>

          {/* 3x3 Rule-of-Thirds Grid Guides */}
          <div className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div className="border-r border-b border-[#0099ff]/30 border-dashed" />
            <div />
          </div>

          {/* 8 Resize Handles with Large 28px Touch Zones */}
          {/* Top-Left */}
          <div
            onPointerDown={(e) => startDrag(e, "nw")}
            className="absolute -top-3.5 -left-3.5 w-7 h-7 flex items-center justify-center cursor-nwse-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Top-Center */}
          <div
            onPointerDown={(e) => startDrag(e, "n")}
            className="absolute -top-3.5 left-1/2 -translate-x-1/2 w-7 h-7 flex items-center justify-center cursor-ns-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Top-Right */}
          <div
            onPointerDown={(e) => startDrag(e, "ne")}
            className="absolute -top-3.5 -right-3.5 w-7 h-7 flex items-center justify-center cursor-nesw-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Middle-Right */}
          <div
            onPointerDown={(e) => startDrag(e, "e")}
            className="absolute top-1/2 -right-3.5 -translate-y-1/2 w-7 h-7 flex items-center justify-center cursor-ew-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Bottom-Right */}
          <div
            onPointerDown={(e) => startDrag(e, "se")}
            className="absolute -bottom-3.5 -right-3.5 w-7 h-7 flex items-center justify-center cursor-nwse-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Bottom-Center */}
          <div
            onPointerDown={(e) => startDrag(e, "s")}
            className="absolute -bottom-3.5 left-1/2 -translate-x-1/2 w-7 h-7 flex items-center justify-center cursor-ns-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Bottom-Left */}
          <div
            onPointerDown={(e) => startDrag(e, "sw")}
            className="absolute -bottom-3.5 -left-3.5 w-7 h-7 flex items-center justify-center cursor-nesw-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>

          {/* Middle-Left */}
          <div
            onPointerDown={(e) => startDrag(e, "w")}
            className="absolute top-1/2 -left-3.5 -translate-y-1/2 w-7 h-7 flex items-center justify-center cursor-ew-resize z-50 pointer-events-auto touch-none"
          >
            <div className="w-4.5 h-4.5 bg-[#0099ff] border-2 border-white rounded-xs shadow-md" />
          </div>
        </div>
      </div>
    </div>
  );
}
