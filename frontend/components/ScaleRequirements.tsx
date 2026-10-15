import { ScaleRequirements as ScalePolicy } from "@/lib/api";

export default function ScaleRequirements({ policy, compact = false }: { policy?: ScalePolicy; compact?: boolean }) {
  if (!policy?.version) return null;
  const tolerance = policy.dimension_tolerances_percent;
  return <section className={`scale-requirements ${compact ? "compact" : ""}`} aria-label="比例设计要求" key={policy.scale}>
    <div className="scale-requirements-heading"><h2>{policy.scale} · {policy.label}</h2>
      {!compact && <span className="secondary">{policy.applied_to_design ? "本设计采用的标准" : "当前标准 · 此设计未记录采用"}</span>}
    </div>
    <p className="secondary scale-description">{policy.description}</p>
    <dl className="scale-summary">
      <div><dt>必需机构</dt><dd>{policy.mechanisms.map(m => `${m.label}${m.minimum_instances > 1 ? ` ×${m.minimum_instances}` : ""}`).join("、")}</dd></div>
      <div><dt>尺寸偏差上限</dt><dd>车长 / 轴距 {tolerance.length}% · 车宽 / 车高 {tolerance.width}%{tolerance.height !== tolerance.width ? ` / ${tolerance.height}%` : ""}</dd></div>
      <div><dt>轮胎偏差上限</dt><dd>外径 {policy.component_tolerances_percent.tyre_diameter}% · 宽度 {policy.component_tolerances_percent.tyre_width}%</dd></div>
      <div><dt>参考与资料</dt><dd>{policy.reference_views.length} 组参考角度 · {policy.required_measurements.length} 项必需尺寸</dd></div>
    </dl>
    <details className="scale-requirements-details"><summary>外观与实物验收要求</summary>
      <dl className="scale-visuals">{policy.visual_requirements.map(item => <div key={item.id}><dt>{item.label}</dt><dd>{item.detail}</dd></div>)}</dl>
      <p className="secondary">实物抽验：{policy.physical_checks.join("、")}。</p>
    </details>
  </section>;
}
