"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getDesign, getDesignStatus,
  customizeDesign, getModsCatalog, openInStudio,
  DesignDetail, DesignPart, ModPartInfo,
} from "@/lib/api";

const MOD_EMOJI: Record<string, string> = {
  aerodynamics: "💨", wheels_stance: "🛞", exhaust: "💨",
  body_kits: "🏎️", interior: "🪑", lighting: "💡",
  paint_finish: "🎨", performance: "⚡",
};

export default function DesignDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [design, setDesign] = useState<DesignDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [customText, setCustomText] = useState("");
  const [customizing, setCustomizing] = useState(false);
  const [customError, setCustomError] = useState("");
  const [openingStudio, setOpeningStudio] = useState(false);
  const [studioOpenResult, setStudioOpenResult] = useState<string>("");
  const [selectedMods, setSelectedMods] = useState<Set<string>>(new Set());
  const [activeCategory, setActiveCategory] = useState("all");
  const [modCatalog, setModCatalog] = useState<Record<string, ModPartInfo[]>>({});

  useEffect(() => { if (!id) return; loadAll(); }, [id]);

  async function loadAll() {
    try {
      const [designData, modsData] = await Promise.all([
        getDesign(id),
        getModsCatalog().catch(() => ({})),
      ]);
      setDesign(designData);
      setModCatalog(modsData);

      if (designData.status === "pending" || designData.status === "processing") {
        pollStatus();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function pollStatus() {
    const interval = setInterval(async () => {
      try {
        const status = await getDesignStatus(id);
        if (status.status === "completed" || status.status === "failed") {
          clearInterval(interval);
          loadAll();
        }
      } catch { clearInterval(interval); }
    }, 3000);
    setTimeout(() => clearInterval(interval), 300_000);
  }

  const toggleMod = (modId: string) => {
    setSelectedMods((prev) => {
      const next = new Set(prev);
      next.has(modId) ? next.delete(modId) : next.add(modId);
      return next;
    });
  };

  const buildCustomText = useCallback(() => {
    if (selectedMods.size === 0) return customText;
    const modLines: string[] = [];
    for (const [cat, mods] of Object.entries(modCatalog)) {
      const selected = mods.filter((m) => selectedMods.has(m.id));
      if (selected.length > 0) {
        modLines.push(`${cat}: ${selected.map((m) => m.name).join(", ")}`);
      }
    }
    const modText = modLines.join("; ");
    return customText ? `${modText}. Also: ${customText}` : modText;
  }, [selectedMods, customText, modCatalog]);

  const handleOpenInStudio = async () => {
    setOpeningStudio(true);
    setStudioOpenResult("");
    try {
      const result = await openInStudio(id);
      if (result.file_opened) {
        setStudioOpenResult("✅ Studio opened! Your design is now in Studio 2.0.");
      } else if (result.studio_opened) {
        setStudioOpenResult("⚠️ Studio opened but couldn't load the file. Try File → Open manually.");
      } else {
        setStudioOpenResult("⚠️ Could not launch Studio. Is it installed at D:\\lego\\Studio 2.0\\?");
      }
    } catch (err: any) {
      setStudioOpenResult("❌ Failed: " + (err.message || "Unknown error"));
    }
    setOpeningStudio(false);
  };

  const handleCustomize = async () => {
    const text = buildCustomText();
    if (!text || text.length < 3) {
      setCustomError("Select mods or describe your customization.");
      return;
    }
    setCustomizing(true);
    setCustomError("");
    try {
      const resp = await customizeDesign(id, text);
      router.push(`/designs/${resp.id}`);
    } catch (err: any) {
      setCustomError(err.message || "Customization failed.");
      setCustomizing(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center">
        <div className="animate-spin h-8 w-8 border-4 border-brick-red border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-gray-600">Loading design...</p>
      </div>
    );
  }

  if (error || !design) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <div className="text-4xl mb-4">⚠️</div>
        <h2 className="text-xl font-bold mb-2">Error</h2>
        <p className="text-gray-600 mb-4">{error || "Not found"}</p>
        <a href="/" className="text-brick-red hover:underline">← Back</a>
      </div>
    );
  }

  const isProcessing = design.status === "pending" || design.status === "processing";
  const isCompleted = design.status === "completed";
  const isCustomization = !!design.parent_design_id;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Breadcrumb + Header */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4 flex-wrap">
        <a href="/" className="hover:text-gray-700">← Home</a>
        {isCustomization && design.parent_design_id && (
          <><span>/</span><a href={`/designs/${design.parent_design_id}`} className="hover:text-gray-700">Base</a></>
        )}
        <span>/</span>
        <span className="font-medium text-gray-900 truncate max-w-[300px]">
          {design.car?.make} {design.car?.model} ({design.car?.year})
          {isCustomization && " 🔧"}
        </span>
        <MatchBadge match={design.match} status={design.status} />
      </div>

      {/* ── STUDIO INTEGRATION ── */}
      <div className="mb-6">
        {isCompleted && design.file_urls?.io ? (
          <div className="bg-gradient-to-br from-blue-600 to-purple-700 rounded-2xl p-8 text-white">
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-4xl">🧱</span>
                  <h2 className="text-2xl font-bold">Open in BrickLink Studio</h2>
                </div>
                <p className="text-blue-100 max-w-lg">
                  Your LEGO car design is ready. Download the .io file and open it in
                  BrickLink Studio 2.0 to view in 3D, generate building instructions,
                  export parts lists, and render photorealistic images.
                </p>
                {design.file_urls?.io && (
                  <div className="flex gap-3 flex-wrap mt-4">
                    <button
                      onClick={handleOpenInStudio}
                      disabled={openingStudio}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-white text-blue-700 font-bold rounded-xl hover:bg-blue-50 transition shadow-lg disabled:opacity-50"
                    >
                      {openingStudio ? "⏳ Launching..." : "🚀 Open in Studio"}
                    </button>
                    <a
                      href={`${process.env.NEXT_PUBLIC_API_URL}/designs/${design.id}/open-in-studio`}
                      className="inline-flex items-center gap-2 px-6 py-3 bg-white/20 text-white font-bold rounded-xl hover:bg-white/30 transition"
                    >
                      📥 Download .io
                    </a>
                  </div>
                )}
                {studioOpenResult && (
                  <p className="mt-3 text-sm text-blue-100">{studioOpenResult}</p>
                )}
              </div>
              <div className="text-right text-blue-100 text-sm">
                <div className="bg-white/10 rounded-lg px-4 py-3">
                  <div className="font-mono text-lg text-white font-bold">
                    {design.parts_count?.toLocaleString() || "?"}
                  </div>
                  <div>Total pieces</div>
                </div>
              </div>
            </div>
            {design.file_urls?.io && (
              <div className="mt-4 pt-4 border-t border-white/20 text-blue-100 text-xs">
                <p className="mb-1">
                  📂 File location: <code className="bg-white/10 px-1 rounded">{design.file_urls.io}</code>
                </p>
                <p>
                  💡 After downloading, open Studio → File → Open → select the .io file.
                  Or double-click the .io file to open directly in Studio.
                </p>
              </div>
            )}
          </div>
        ) : isProcessing ? (
          <div className="bg-gray-900 rounded-xl p-8 flex items-center justify-center">
            <div className="text-center text-white/70">
              <div className="animate-spin h-10 w-10 border-4 border-brick-red border-t-transparent rounded-full mx-auto mb-4" />
              <p className="font-medium text-lg">
                {isCustomization ? "Applying customizations..." : "Generating Studio file..."}
              </p>
              <p className="text-sm mt-2 text-white/50 max-w-md">
                Claude is designing your LEGO car model as a BrickLink Studio .io file.
                You&rsquo;ll be able to open it directly in Studio.
              </p>
            </div>
          </div>
        ) : (
          <div className="bg-gray-100 rounded-xl p-8 flex items-center justify-center text-gray-400">
            <div className="text-center">
              <p className="text-5xl mb-3">🧱</p>
              <p className="font-medium">Studio .io file will appear here</p>
              <p className="text-sm mt-1">Once generation completes, you can open it in BrickLink Studio</p>
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── LEFT: Stats + Export + Parts ── */}
        <div className="lg:col-span-1 space-y-4">
          {/* Stats card */}
          <div className="bg-white rounded-xl shadow p-5">
            <h3 className="font-bold text-lg mb-3">📊 Overview</h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <div><div className="text-2xl font-bold">{design.parts_count?.toLocaleString() || "?"}</div><div className="text-xs text-gray-500">Pieces</div></div>
              <div><div className="text-2xl font-bold">{design.difficulty || "?"}</div><div className="text-xs text-gray-500">Difficulty</div></div>
              <div><div className="text-2xl font-bold">{design.match?.label || "?"}</div><div className="text-xs text-gray-500">Match</div></div>
              <div><div className="text-2xl font-bold">{isCustomization ? "Custom" : "Original"}</div><div className="text-xs text-gray-500">Type</div></div>
            </div>
            {design.customization_request && (
              <div className="mt-3 bg-purple-50 rounded-lg p-3 text-xs text-purple-700">
                <strong>Request:</strong> &ldquo;{design.customization_request}&rdquo;
              </div>
            )}
          </div>

          {/* Export buttons */}
          {isCompleted && (
            <div className="bg-white rounded-xl shadow p-5">
              <h3 className="font-bold text-sm mb-3">📦 Export Files</h3>
              <div className="space-y-2">
                {[
                  ["🛒 BrickLink XML", `/api/v1/export/xml/${design.id}`],
                  ["📊 Parts CSV", `/api/v1/export/csv/${design.id}`],
                  ["📐 LDraw File", `/api/v1/export/ldr/${design.id}`],
                  ["🧱 Studio .io", `/api/v1/export/io/${design.id}`],
                ].map(([label, href]) => (
                  <a key={label} href={`${process.env.NEXT_PUBLIC_API_URL}${href}`}
                    target="_blank"
                    className="block w-full px-3 py-2 bg-gray-50 hover:bg-gray-100 rounded-lg text-sm font-medium text-gray-700 transition text-center">
                    {label}
                  </a>
                ))}
              </div>
            </div>
          )}

          {/* Parts list (compact) */}
          {design.parts && design.parts.length > 0 && (
            <div className="bg-white rounded-xl shadow p-5">
              <h3 className="font-bold text-sm mb-3">🧱 Parts ({design.parts.length})</h3>
              <div className="max-h-[300px] overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-gray-500 border-b">
                      <th className="text-left py-1">Part</th>
                      <th className="text-right py-1">Qty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {design.parts.slice(0, 30).map((p, i) => (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="py-1 font-mono">{p.part_num}</td>
                        <td className="py-1 text-right">{p.quantity}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Customization Panel ── */}
        <div className="lg:col-span-2 space-y-4">
          {isCompleted && (
            <div className="bg-white rounded-xl shadow p-5">
              <h2 className="font-bold text-lg mb-4">🔧 Customize This Build</h2>

              {/* Category tabs */}
              <div className="flex gap-1 flex-wrap mb-4">
                <CategoryTab active={activeCategory === "all"} onClick={() => setActiveCategory("all")} label="All" count={Object.values(modCatalog).flat().length} />
                {Object.entries(modCatalog).map(([catId, mods]) => (
                  <CategoryTab key={catId} active={activeCategory === catId}
                    onClick={() => setActiveCategory(catId)}
                    label={`${MOD_EMOJI[catId] || ""} ${catId.replace(/_/g, " ")}`}
                    count={mods.length} />
                ))}
              </div>

              {/* Mod parts grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[400px] overflow-y-auto mb-4">
                {Object.entries(modCatalog)
                  .filter(([cat]) => activeCategory === "all" || cat === activeCategory)
                  .flatMap(([cat, mods]) => mods.map((m) => ({ ...m, cat })))
                  .map((mod) => (
                    <button key={mod.id}
                      onClick={() => toggleMod(mod.id)}
                      className={`text-left p-3 rounded-xl border-2 transition ${
                        selectedMods.has(mod.id)
                          ? "border-brick-red bg-red-50 shadow-md"
                          : "border-gray-200 hover:border-gray-300 bg-white"
                      }`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-sm truncate">
                            {selectedMods.has(mod.id) && "✓ "}{mod.name}
                          </div>
                          <div className="text-xs text-gray-500 mt-0.5">{mod.real_world_ref}</div>
                        </div>
                        <span className={`text-xs px-1.5 py-0.5 rounded ml-2 ${
                          mod.difficulty === "easy" ? "bg-green-100 text-green-700" :
                          mod.difficulty === "medium" ? "bg-yellow-100 text-yellow-700" :
                          "bg-red-100 text-red-700"
                        }`}>{mod.difficulty}</span>
                      </div>
                      <div className="text-xs text-gray-600 mt-1 line-clamp-2">{mod.description}</div>
                      <div className="flex items-center justify-between mt-1.5 text-xs text-gray-400">
                        <span>{MOD_EMOJI[mod.cat] || ""} {mod.cat.replace(/_/g, " ")}</span>
                        <span>~{mod.estimated_parts} parts</span>
                      </div>
                    </button>
                  ))}
              </div>

              {/* Selected mods summary + custom text */}
              {selectedMods.size > 0 && (
                <div className="bg-blue-50 rounded-lg p-3 mb-3 text-sm">
                  <strong>Selected:</strong>{" "}
                  {[...selectedMods].map((mid) => {
                    for (const mods of Object.values(modCatalog)) {
                      const m = mods.find((x) => x.id === mid);
                      if (m) return m.name;
                    }
                    return mid;
                  }).join(", ")}
                </div>
              )}

              <div className="flex gap-3">
                <input type="text" value={customText}
                  onChange={(e) => setCustomText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCustomize()}
                  placeholder='Or describe what you want: "Add a carbon fiber hood, lower the stance, black wheels"'
                  className="flex-1 border border-gray-300 rounded-xl px-4 py-2.5 text-sm focus:ring-2 focus:ring-brick-red outline-none" />
                <button onClick={handleCustomize}
                  disabled={customizing || (selectedMods.size === 0 && customText.trim().length < 3)}
                  className="px-6 py-2.5 bg-brick-red hover:bg-red-700 text-white font-bold rounded-xl transition disabled:opacity-50 whitespace-nowrap">
                  {customizing ? "Processing..." : "🔧 Customize"}
                </button>
              </div>
              {customError && <p className="text-red-600 text-xs mt-2">{customError}</p>}
            </div>
          )}

          {/* Processing state */}
          {isProcessing && (
            <div className="bg-white rounded-xl shadow p-8 text-center">
              <div className="animate-spin h-10 w-10 border-4 border-brick-red border-t-transparent rounded-full mx-auto mb-4" />
              <h3 className="font-bold text-lg mb-2">
                {isCustomization ? "Applying Customizations..." : "Generating Design..."}
              </h3>
              <p className="text-gray-500 text-sm">
                Claude is designing your {isCustomization ? "customized" : ""} LEGO car.
                The 3D preview will update when complete.
              </p>
            </div>
          )}

          {/* Failed state */}
          {design.status === "failed" && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
              <p className="text-red-800 font-medium">Generation failed</p>
              <p className="text-red-600 text-sm mt-1">{design.error_message}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────

function CategoryTab({ active, onClick, label, count }: {
  active: boolean; onClick: () => void; label: string; count: number;
}) {
  return (
    <button onClick={onClick}
      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
        active ? "bg-brick-red text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
      }`}>
      {label} <span className="opacity-70">({count})</span>
    </button>
  );
}

function MatchBadge({ match, status }: { match?: DesignDetail["match"]; status: string }) {
  if (!match) return null;
  const colors: Record<number, string> = {
    1: "bg-green-100 text-green-800", 2: "bg-blue-100 text-blue-800",
    3: "bg-yellow-100 text-yellow-800", 4: "bg-purple-100 text-purple-800",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colors[match.level] || colors[4]}`}>
      {match.level === 1 && "🏭"} {match.level === 2 && "👤"}
      {match.level === 3 && "📐"} {match.level === 4 && "🤖"}
      {match.label} • {Math.round(match.confidence * 100)}%
    </span>
  );
}
