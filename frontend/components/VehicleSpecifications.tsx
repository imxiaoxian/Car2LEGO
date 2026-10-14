"use client";

import { useState } from "react";
import { ExternalLink, LoaderCircle, RefreshCw } from "lucide-react";
import { CarResult, collectVehicleSpecifications, PhysicalSpecifications, ScaleRequirements } from "@/lib/api";

const names: Record<string, string> = {
  length: "车身长度", width: "车身宽度（不含后视镜）", height: "车身高度", wheelbase: "轴距",
  front_track: "前轮距", rear_track: "后轮距", front_tyre_diameter: "前轮胎外径", rear_tyre_diameter: "后轮胎外径",
  front_tyre_width: "前轮胎宽度", rear_tyre_width: "后轮胎宽度", front_rim_diameter: "前轮毂直径", rear_rim_diameter: "后轮毂直径",
  door_length: "车门长度", door_height: "车门高度（含玻璃）", door_opening_angle: "车门开启角",
  windshield_width: "前风挡宽度", windshield_height: "前风挡斜高", windshield_rake: "前风挡倾角（相对水平面）",
  seat_width: "座椅宽度", engine_length: "发动机长度", engine_width: "发动机宽度", engine_height: "发动机高度",
};

export default function VehicleSpecifications({ car, scale, data, requirements }: {
  car: CarResult; scale: string; data?: PhysicalSpecifications; requirements?: ScaleRequirements;
}) {
  const [collected, setCollected] = useState<PhysicalSpecifications | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const specs = collected || data;
  const measurements = Object.entries(specs?.measurements || {});
  const required = requirements?.required_measurements || specs?.required_measurements;
  const missingRequired = required?.filter(name => !specs?.measurements[name]?.grounded) || [];

  async function collect() {
    setBusy(true); setError("");
    try { setCollected({ ...await collectVehicleSpecifications(car.make, car.model, car.year, scale), applied_to_design: false }); }
    catch (err) { setError(err instanceof Error ? err.message : "尺寸资料采集失败"); }
    finally { setBusy(false); }
  }

  return <section className="physical-specifications" aria-label="车型物理资料">
    <div className="section-heading"><h2>车型物理资料</h2><div className="physical-spec-actions">
      <span className="secondary">{specs?.applied_to_design ? "此设计采用的资料" : "尚未用于此设计"}</span>
      <button className="icon-button" title="采集车型尺寸资料" aria-label="采集车型尺寸资料" disabled={busy} onClick={() => void collect()}>
        {busy ? <LoaderCircle size={18} className="spin" /> : <RefreshCw size={18} />}
      </button></div></div>
    {error && <p className="error-message" role="alert">{error}</p>}
    {measurements.length > 0 ? <div className="parts-table-wrap"><table className="parts-table physical-spec-table">
      <thead><tr><th>项目</th><th>要求</th><th>实车</th><th>{scale} 目标</th><th>资料状态</th><th>来源</th></tr></thead>
      <tbody>{measurements.map(([name, m]) => <tr key={name}><td>{names[name] || name}</td>
        <td>{required ? required.includes(name) ? "必需" : "辅助" : "未分类"}</td>
        <td>{m.value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {m.unit === "deg" ? "°" : m.unit}</td>
        <td>{m.unit === "deg" ? `${m.value}°` : m.target_model_mm == null ? "待换算" : `${m.target_model_mm.toFixed(2)} mm`}</td>
        <td>{m.conflicted ? "来源冲突" : m.method === "estimated" ? "估算" : m.grounded ? m.method === "derived" ? "规格换算" : "有据可查" : "来源或年款待核"}</td>
        <td>{m.source_url ? <a className="text-link" href={m.source_url} target="_blank" rel="noreferrer" title={m.evidence}>资料<ExternalLink size={12} /></a> : "缺少来源"}</td>
      </tr>)}</tbody></table></div> : <p className="secondary">尚无可用的尺寸资料</p>}
    {!!specs?.conflicts.length && <p className="error-message">{specs.conflicts.length} 项资料存在数值冲突，未作为精确尺寸约束。</p>}
    {!!missingRequired.length && <details className="quality-issues"><summary>{scale} 必需资料待核 · {missingRequired.length} 项</summary>
      <p className="secondary physical-missing">{missingRequired.map(name => names[name] || name).join("、")}</p>
    </details>}
    {!!specs?.missing.length && <details className="quality-issues"><summary>缺失资料 · {specs.missing.length} 项</summary>
      <p className="secondary physical-missing">{specs.missing.map(name => names[name] || name).join("、")}</p>
    </details>}
    {!!specs?.sources.length && <details className="quality-issues physical-sources"><summary>资料来源 · {specs.sources.length} 项</summary>
      {specs.sources.map((source, index) => <div key={`${source.url}-${index}`}><a className="text-link" href={source.url} target="_blank" rel="noreferrer">{source.title || new URL(source.url).hostname}<ExternalLink size={12} /></a>
        <span className="secondary">{source.status === "fetched" ? "已读取" : "暂不可用"}</span>{source.note && <span className="secondary">车型版本待核对</span>}</div>)}
    </details>}
  </section>;
}
