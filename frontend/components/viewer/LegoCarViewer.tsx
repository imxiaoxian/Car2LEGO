"use client";

import { useRef, useMemo, useState, useCallback, Suspense } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import {
  OrbitControls,
  Grid,
  Environment,
  PerspectiveCamera,
  Html,
} from "@react-three/drei";
import * as THREE from "three";

// ── LDraw Parser ──────────────────────────────────

interface LDrawLine {
  type: "comment" | "step" | "part" | "file" | "nofile";
  raw: string;
  // Part data
  color?: number;
  x?: number;
  y?: number;
  z?: number;
  rotMatrix?: number[]; // 9 values
  partFile?: string;
}

interface BrickData {
  id: string;
  color: number;
  position: [number, number, number];
  rotation: THREE.Euler;
  partFile: string;
  size: [number, number, number]; // width, height, depth in LDU
  stepIndex: number;
}

function parseLDraw(ldrContent: string): { bricks: BrickData[]; steps: number } {
  const lines = ldrContent.split("\n");
  const bricks: BrickData[] = [];
  let currentStep = 0;
  let currentFile: string | null = null;

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    if (line.startsWith("0 STEP")) {
      currentStep++;
      continue;
    }
    if (line.startsWith("0 FILE ")) {
      currentFile = line.substring(7).trim().toLowerCase();
      continue;
    }
    if (line.startsWith("0 NOFILE")) {
      currentFile = null;
      continue;
    }
    if (line.startsWith("0")) continue; // skip other comments

    // Part reference: 1 <color> <x> <y> <z> <a>..<i> <part.dat>
    if (line.startsWith("1 ")) {
      const parts = line.split(/\s+/);
      if (parts.length < 15) continue;

      const color = parseInt(parts[1]);
      const x = parseFloat(parts[2]);
      const y = parseFloat(parts[3]);
      const z = parseFloat(parts[4]);
      const rot = [
        parseFloat(parts[5]), parseFloat(parts[6]), parseFloat(parts[7]),
        parseFloat(parts[8]), parseFloat(parts[9]), parseFloat(parts[10]),
        parseFloat(parts[11]), parseFloat(parts[12]), parseFloat(parts[13]),
      ];
      const partFile = parts[14]?.replace(/\\/g, "/").split("/").pop() || "3001.dat";

      // Estimate brick size from part name
      const size = estimatePartSize(partFile);

      // Convert LDraw coords to Three.js:
      // LDraw: X=left-right, Y=up, Z=front-back (LDU)
      // Three.js: X=right, Y=up, Z=towards-camera
      // So: LDraw X → Three -X, LDraw Z → Three Z (swap signs for visual)
      const pos: [number, number, number] = [
        -x / 20, // LDU → studs, flip X
        y / 20,
        z / 20,
      ];

      // Rotation matrix → Euler
      const matrix4 = new THREE.Matrix4();
      matrix4.set(
        rot[0], rot[3], rot[6], 0,
        rot[1], rot[4], rot[7], 0,
        rot[2], rot[5], rot[8], 0,
        0, 0, 0, 1,
      );
      const euler = new THREE.Euler().setFromRotationMatrix(matrix4);

      bricks.push({
        id: `${currentStep}-${bricks.length}`,
        color,
        position: pos,
        rotation: euler,
        partFile,
        size: [size[0] / 20, size[1] / 20, size[2] / 20], // LDU → studs
        stepIndex: currentStep,
      });
    }
  }

  return { bricks, steps: currentStep + 1 };
}

// Estimate brick/part dimensions in LDU based on filename
function estimatePartSize(partFile: string): [number, number, number] {
  const name = partFile.toLowerCase();
  // Common parts
  if (name.includes("3024")) return [20, 8, 20];        // plate 1x1
  if (name.includes("3023")) return [20, 8, 40];        // plate 1x2
  if (name.includes("3022")) return [40, 8, 40];        // plate 2x2
  if (name.includes("3021")) return [40, 8, 60];        // plate 2x3
  if (name.includes("3020")) return [40, 8, 80];        // plate 2x4
  if (name.includes("3666")) return [20, 8, 120];       // plate 1x6
  if (name.includes("3460")) return [20, 8, 160];       // plate 1x8
  if (name.includes("3795")) return [40, 8, 120];       // plate 2x6
  if (name.includes("3034")) return [40, 8, 160];       // plate 2x8
  if (name.includes("3035")) return [80, 8, 160];       // plate 4x8
  if (name.includes("4282")) return [40, 8, 320];       // plate 2x16

  if (name.includes("3005")) return [20, 24, 20];       // brick 1x1
  if (name.includes("3004")) return [20, 24, 40];       // brick 1x2
  if (name.includes("3622")) return [20, 24, 60];       // brick 1x3
  if (name.includes("3010")) return [20, 24, 80];       // brick 1x4
  if (name.includes("3009")) return [20, 24, 120];      // brick 1x6
  if (name.includes("3008")) return [20, 24, 160];      // brick 1x8
  if (name.includes("3003")) return [40, 24, 40];       // brick 2x2
  if (name.includes("3002")) return [40, 24, 60];       // brick 2x3
  if (name.includes("3001")) return [40, 24, 80];       // brick 2x4
  if (name.includes("2456")) return [40, 24, 120];      // brick 2x6

  if (name.includes("3069")) return [20, 8, 40];        // tile 1x2
  if (name.includes("3070")) return [20, 8, 20];        // tile 1x1
  if (name.includes("2431")) return [20, 8, 80];        // tile 1x4
  if (name.includes("3068")) return [40, 8, 40];        // tile 2x2
  if (name.includes("87079")) return [40, 8, 80];       // tile 2x4

  // Slopes
  if (name.includes("4286")) return [20, 20, 60];       // slope 33 3x1
  if (name.includes("4287")) return [20, 20, 60];       // slope inv
  if (name.includes("3298")) return [40, 20, 60];       // slope 33 3x2
  if (name.includes("3297")) return [40, 20, 80];       // slope 33 3x4
  if (name.includes("3040")) return [20, 20, 40];       // slope 45 2x1
  if (name.includes("3041")) return [40, 20, 40];       // slope 45 2x2
  if (name.includes("3039")) return [40, 20, 40];       // slope 45 double
  if (name.includes("11477")) return [20, 16, 40];      // curved slope 2x1
  if (name.includes("15068")) return [40, 16, 40];      // curved slope 2x2
  if (name.includes("50950")) return [20, 16, 60];      // curved slope 3x1

  // Wheels
  if (name.includes("4624")) return [30, 30, 10];       // wheel small
  if (name.includes("6014")) return [40, 40, 12];       // wheel large
  if (name.includes("3641")) return [30, 30, 10];       // tire
  if (name.includes("6015")) return [40, 40, 12];       // tire

  // Windscreens
  if (name.includes("3823")) return [40, 40, 80];       // windscreen
  if (name.includes("2437")) return [60, 26, 80];       // low windscreen
  if (name.includes("4176")) return [40, 40, 120];      // wide windscreen

  // Default: assume 1x1 plate
  return [20, 8, 20];
}

// ── LDraw Color → Hex ────────────────────────────

const LDRAW_COLORS: Record<number, string> = {
  0: "#05131D", 1: "#0055BF", 2: "#257A3E", 4: "#C91A09",
  5: "#C870A0", 6: "#583927", 7: "#9BA19D", 8: "#6D6E5C",
  9: "#B4D2E3", 10: "#4B9F4A", 12: "#F2705E", 13: "#FC97AC",
  14: "#F2CD37", 15: "#FFFFFF", 17: "#C2DAB8", 19: "#E4CD9E",
  22: "#81007B", 25: "#FE8A18", 26: "#923978", 27: "#BBE90B",
  28: "#958A73", 68: "#F3CF9B", 70: "#582A12", 71: "#A0A5A9",
  72: "#6C6E68", 73: "#5C9DD1", 74: "#73DCA1", 77: "#FECCCF",
  78: "#F6D7B3", 84: "#CC702A", 85: "#3F3691", 86: "#7C503A",
  89: "#4C61DB", 92: "#D09168",
};

function getColorHex(ldrawColor: number): string {
  return LDRAW_COLORS[ldrawColor] || "#CCCCCC";
}

// ── Brick mesh component ─────────────────────────

function LegoBrick({ brick, highlight }: { brick: BrickData; highlight?: boolean }) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const colorHex = getColorHex(brick.color);
  const [hovered, setHovered] = useState(false);

  const edgeColor = highlight || hovered ? "#FFD700" : "#333333";

  return (
    <mesh
      ref={meshRef}
      position={brick.position}
      rotation={brick.rotation}
      onPointerOver={(e) => { e.stopPropagation(); setHovered(true); }}
      onPointerOut={() => setHovered(false)}
    >
      <boxGeometry args={brick.size} />
      <meshStandardMaterial
        color={colorHex}
        roughness={0.3}
        metalness={0.05}
      />
      <lineSegments>
        <edgesGeometry args={[new THREE.BoxGeometry(...brick.size)]} />
        <lineBasicMaterial color={edgeColor} linewidth={1} />
      </lineSegments>
    </mesh>
  );
}

// ── Car model component ──────────────────────────

function CarModel({
  bricks,
  currentStep,
  showAllSteps,
  highlightModified,
  modifiedIndices,
}: {
  bricks: BrickData[];
  currentStep: number;
  showAllSteps: boolean;
  highlightModified: boolean;
  modifiedIndices: Set<number>;
}) {
  const visibleBricks = useMemo(() => {
    if (showAllSteps) return bricks;
    return bricks.filter((b) => b.stepIndex <= currentStep);
  }, [bricks, currentStep, showAllSteps]);

  return (
    <group>
      {visibleBricks.map((brick, idx) => (
        <LegoBrick
          key={brick.id}
          brick={brick}
          highlight={highlightModified && modifiedIndices.has(idx)}
        />
      ))}
    </group>
  );
}

// ── Loading fallback ─────────────────────────────

function LoadingFallback() {
  return (
    <Html center>
      <div className="text-gray-400 text-sm">
        <div className="animate-spin h-6 w-6 border-2 border-brick-red border-t-transparent rounded-full mx-auto mb-2" />
        Loading 3D model...
      </div>
    </Html>
  );
}

// ── Main Viewer Component ────────────────────────

interface LegoCarViewerProps {
  ldrContent: string;
  modifiedLdrContent?: string; // For before/after comparison
  className?: string;
}

export default function LegoCarViewer({
  ldrContent,
  modifiedLdrContent,
  className = "",
}: LegoCarViewerProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [showAllSteps, setShowAllSteps] = useState(true);
  const [showModified, setShowModified] = useState(false);
  const [viewMode, setViewMode] = useState<"original" | "modified" | "split">("original");

  const originalData = useMemo(() => parseLDraw(ldrContent), [ldrContent]);
  const modifiedData = useMemo(
    () => (modifiedLdrContent ? parseLDraw(modifiedLdrContent) : null),
    [modifiedLdrContent]
  );

  const activeData = showModified && modifiedData ? modifiedData : originalData;

  // Simple diff: mark bricks in modified that differ from original
  const modifiedIndices = useMemo(() => {
    const indices = new Set<number>();
    if (modifiedData && originalData) {
      modifiedData.bricks.forEach((b, i) => {
        const match = originalData.bricks.find(
          (ob) =>
            ob.partFile === b.partFile &&
            ob.color === b.color &&
            Math.abs(ob.position[0] - b.position[0]) < 0.1 &&
            Math.abs(ob.position[1] - b.position[1]) < 0.1 &&
            Math.abs(ob.position[2] - b.position[2]) < 0.1
        );
        if (!match) indices.add(i);
      });
    }
    return indices;
  }, [modifiedData, originalData]);

  const maxSteps = activeData.steps;
  const hasModified = !!modifiedData;

  return (
    <div className={`relative rounded-xl overflow-hidden bg-gray-900 ${className}`}>
      {/* Controls bar */}
      <div className="absolute top-3 left-3 right-3 z-10 flex flex-wrap gap-2">
        {/* Step controls */}
        <div className="flex items-center gap-1 bg-black/60 backdrop-blur rounded-lg px-3 py-1.5 text-white text-xs">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            className="px-2 py-0.5 hover:bg-white/20 rounded transition"
            disabled={currentStep === 0}
          >
            ◀
          </button>
          <span className="font-mono min-w-[60px] text-center">
            {showAllSteps ? "All" : `Step ${currentStep + 1}/${maxSteps}`}
          </span>
          <button
            onClick={() => setCurrentStep(Math.min(maxSteps - 1, currentStep + 1))}
            className="px-2 py-0.5 hover:bg-white/20 rounded transition"
            disabled={currentStep >= maxSteps - 1}
          >
            ▶
          </button>
        </div>

        <button
          onClick={() => setShowAllSteps(!showAllSteps)}
          className={`px-2 py-1 rounded text-xs transition ${
            showAllSteps
              ? "bg-white/20 text-white"
              : "bg-brick-red text-white"
          }`}
        >
          {showAllSteps ? "All Steps" : "Step-by-Step"}
        </button>

        {/* View mode toggle (only when modified data available) */}
        {hasModified && (
          <>
            <div className="h-6 w-px bg-white/20" />
            <button
              onClick={() => { setShowModified(false); setViewMode("original"); }}
              className={`px-2 py-1 rounded text-xs transition ${
                !showModified ? "bg-blue-600 text-white" : "bg-white/10 text-white/70"
              }`}
            >
              Original
            </button>
            <button
              onClick={() => { setShowModified(true); setViewMode("modified"); }}
              className={`px-2 py-1 rounded text-xs transition ${
                showModified ? "bg-purple-600 text-white" : "bg-white/10 text-white/70"
              }`}
            >
              Modified ✨
            </button>
          </>
        )}

        {/* Modified parts count */}
        {hasModified && showModified && (
          <span className="px-2 py-1 bg-yellow-500/80 text-black rounded text-xs font-medium">
            {modifiedIndices.size} parts changed
          </span>
        )}

        {/* Reset camera */}
        <button
          onClick={() => {
            // Trigger camera reset via key
            window.dispatchEvent(new KeyboardEvent("keydown", { key: "r" }));
          }}
          className="ml-auto px-2 py-1 bg-white/10 hover:bg-white/20 text-white/70 rounded text-xs transition"
          title="Reset camera view"
        >
          🔄 Reset
        </button>
      </div>

      {/* 3D Canvas */}
      <Canvas
        style={{ height: "500px" }}
        gl={{ antialias: true, alpha: false }}
      >
        <Suspense fallback={<LoadingFallback />}>
          <PerspectiveCamera makeDefault position={[15, 8, 20]} fov={45} />
          <OrbitControls
            target={[0, 2, 7]}
            enableDamping
            dampingFactor={0.1}
            minDistance={5}
            maxDistance={50}
          />
          <ambientLight intensity={0.5} />
          <directionalLight position={[10, 20, 10]} intensity={0.8} castShadow />
          <directionalLight position={[-5, 10, -5]} intensity={0.3} />
          <hemisphereLight args={["#ffffff", "#404060", 0.4]} />
          <Grid
            args={[30, 30]}
            position={[0, -0.01, 7]}
            cellSize={1}
            cellThickness={0.5}
            cellColor="#444444"
            sectionSize={5}
            sectionThickness={1}
            sectionColor="#666666"
            fadeDistance={40}
            infiniteGrid
          />
          <CarModel
            bricks={activeData.bricks}
            currentStep={currentStep}
            showAllSteps={showAllSteps}
            highlightModified={showModified && hasModified}
            modifiedIndices={modifiedIndices}
          />
          <Environment preset="city" />
        </Suspense>
      </Canvas>

      {/* Info bar */}
      <div className="absolute bottom-3 left-3 right-3 flex justify-between text-white/50 text-xs">
        <span>{originalData.bricks.length.toLocaleString()} bricks</span>
        <span>🖱 Drag to rotate • Scroll to zoom • Right-drag to pan</span>
        <span>{maxSteps} steps</span>
      </div>
    </div>
  );
}
