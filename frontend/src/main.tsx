import { useEffect, useRef, useState, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, Blocks, Box, Download, ExternalLink, Image, LoaderCircle, RefreshCw, Search } from "lucide-react";
import BrandSelector from "@/components/BrandSelector";
import { vehicleBrands } from "@/lib/vehicle-brands";
import "./styles.css";

interface Policy { scale: string; required_measurements: string[]; max_parts_per_step: number }
interface Config { scales: Policy[]; colors: { code: number; name: string }[] }
interface Job {
  id: string; status: string; error: string | null; files: Record<string, string>; log: string;
  request: { brand_zh: string; model: string; scale: string };
}
interface Identity { brand: string; model: string; variant: string }
interface Measurement { value: number | null; unit: string; status: string; source: string | null; evidence: string; note: string }
interface Spec { model: string; variant: string; measurements: Record<string, Measurement>; sources: Record<string, { title: string; url: string; kind: string }> }
interface Research { id: string; status: string; request: Identity; spec?: Spec; questions?: string[]; notes?: string[]; error: string | null; cached?: boolean }
interface Plan { grid: { length_studs: number; width_studs: number }; policy: Policy; missing_measurements: string[];
  generation: { draft_recipe_available: boolean; blockers: string[] } }
const identityKey = (value: Identity) => [value.brand, value.model, value.variant].map(item => item.trim().toLowerCase()).join("\n");
const measurementNames: Record<string, string> = {
  length: "车长", width: "车身宽度", height: "车高", wheelbase: "轴距", front_track: "前轮距", rear_track: "后轮距",
  front_overhang: "前悬", rear_overhang: "后悬", door_length: "车门长度", door_panel_height: "门板高度",
  door_front_x: "车门前缘位置", windscreen_bottom_x: "前窗底部位置", windscreen_bottom_width: "前窗底宽",
  windscreen_top_width: "前窗顶宽", windscreen_slant_height: "前窗斜高", seat_width: "座椅宽度",
  engine_length: "发动机长度", engine_width: "发动机宽度", engine_height: "发动机高度",
  windscreen_angle_to_horizontal: "前窗与水平面夹角", door_opening_angle: "车门开启角度",
  front_tyre_width: "前胎宽度", rear_tyre_width: "后胎宽度", front_tyre_aspect: "前胎扁平比", rear_tyre_aspect: "后胎扁平比",
  front_rim_diameter: "前轮毂直径", rear_rim_diameter: "后轮毂直径",
};
const scaleDescriptions: Record<string, string> = {
  "1:38": "外观识别 · 透明座舱 · 四轮滚动",
  "1:24": "完整外观 · 简化内饰 · 前后盖开合",
  "1:16": "精细座舱 · 双门开合 · 转向",
  "1:12": "分层车身 · 精细底盘 · 独立悬挂",
};
const swatches: Record<number, string> = { 4: "#c82a34", 0: "#202124", 15: "#ffffff", 1: "#226bc0", 14: "#f0ce3c", 2: "#267851" };
const statusNames: Record<string, string> = { running: "生成中", completed: "草稿已生成", failed: "生成失败", interrupted: "任务已中断" };

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败");
  return data;
}

function App() {
  const [config, setConfig] = useState<Config>();
  const [brand, setBrand] = useState("Ferrari");
  const [custom, setCustom] = useState(false);
  const [model, setModel] = useState("F40");
  const [variant, setVariant] = useState("");
  const [edited, setEdited] = useState(false);
  const [research, setResearch] = useState<Research>();
  const [startingResearch, setStartingResearch] = useState(false);
  const [researchError, setResearchError] = useState("");
  const attempted = useRef("");
  const [plan, setPlan] = useState<Plan>();
  const [planKey, setPlanKey] = useState("");
  const [planError, setPlanError] = useState("");
  const [scale, setScale] = useState("1:24");
  const [length, setLength] = useState(24);
  const [color, setColor] = useState(4);
  const [description, setDescription] = useState("");
  const [seed, setSeed] = useState(42);
  const [job, setJob] = useState<Job>();
  const [jobId, setJobId] = useState(() => localStorage.getItem("car2lego3d.job") || "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const busy = submitting || job?.status === "running";
  const identity = { brand, model, variant };
  const key = identityKey(identity);
  const searching = startingResearch || research?.status === "running";
  const currentResearch = research && identityKey(research.request) === key ? research : undefined;
  const spec = !startingResearch && currentResearch?.status === "ready" ? currentResearch.spec : undefined;
  const selectionKey = `${key}\n${currentResearch?.id}\n${scale}\n${length}`;
  const currentPlan = planKey === selectionKey ? plan : undefined;
  const policy = config?.scales.find(item => item.scale === scale);
  const blocked = !spec || !currentPlan?.generation.draft_recipe_available;

  async function searchSpecs(refresh = false) {
    if (searching || !brand.trim() || !model.trim()) return;
    attempted.current = key;
    setStartingResearch(true); setResearchError("");
    try {
      const result = await api<Research>("/api/research", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...identity, custom, refresh }) });
      setResearch(result);
    } catch (e) { setResearchError((e as Error).message); }
    finally { setStartingResearch(false); }
  }

  useEffect(() => {
    if (!edited || searching || !brand.trim() || !model.trim() || attempted.current === key) return;
    const timer = setTimeout(() => { void searchSpecs(); }, 1600);
    return () => clearTimeout(timer);
  }, [key, edited, searching]);

  useEffect(() => {
    if (!research || research.status !== "running") return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api<Research>(`/api/research/${research.id}`);
        if (!active) return;
        setResearch(result);
        if (result.status === "running") timer = setTimeout(poll, 1500);
      } catch (e) {
        if (!active) return;
        setResearchError((e as Error).message);
        timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [research?.id]);

  useEffect(() => {
    setPlan(undefined); setPlanError("");
    if (!spec || !currentResearch) return;
    let active = true;
    api<Plan>("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...identity, custom, research_id: currentResearch.id, scale, length_studs: length }) })
      .then(result => { if (active) { setPlan(result); setPlanKey(selectionKey); } }).catch(e => { if (active) setPlanError(e.message); });
    return () => { active = false; };
  }, [key, currentResearch?.id, spec, scale, length]);

  function identityEdited() { setEdited(true); setResearchError(""); setError(""); }

  useEffect(() => { api<Config>("/api/config").then(setConfig).catch(e => setError(e.message)); }, []);
  useEffect(() => {
    if (!jobId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api<Job>(`/api/jobs/${jobId}`);
        if (!active) return;
        setJob(result);
        if (result.status === "running") timer = setTimeout(poll, 1500);
      } catch (e) {
        if (!active) return;
        setError((e as Error).message);
        timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => { active = false; clearTimeout(timer); };
  }, [jobId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || blocked) return;
    setError("");
    if (!brand.trim()) { setError("请选择品牌。"); return; }
    setSubmitting(true);
    try {
      const result = await api<Job>("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...identity, custom, research_id: currentResearch?.id, scale, length_studs: length, color, seed, description }) });
      setJob(result);
      setJobId(result.id);
      localStorage.setItem("car2lego3d.job", result.id);
    } catch (e) { setError((e as Error).message); }
    finally { setSubmitting(false); }
  }

  return <>
    <header className="site-header"><div className="site-nav"><span className="wordmark"><Blocks size={22} />Car2LEGO_3D</span>
      <span className="local-status"><span />本地研究项目</span></div></header>
    <main className="workspace">
      <section className="configuration" aria-labelledby="create-title">
        <div className="section-heading"><h1 id="create-title">创建汽车模型</h1><span>{vehicleBrands.length} 个品牌</span></div>
        <form onSubmit={submit}>
          <fieldset disabled={busy}>
            <BrandSelector value={brand} custom={custom} disabled={busy} onChange={(value, isCustom) => {
              if (isCustom !== custom || (!isCustom && value !== brand)) { setModel(""); setVariant(""); }
              setBrand(value); setCustom(isCustom); identityEdited();
            }} />
            <label className="field"><span>车型</span><input aria-label="车型" value={model} onChange={e => { setModel(e.target.value); identityEdited(); }}
              placeholder="F40" required maxLength={64} /></label>
            <label className="field"><span>年款 / 版本（可选）</span><input aria-label="年款 / 版本" value={variant}
              onChange={e => { setVariant(e.target.value); identityEdited(); }} placeholder="如 1987 · 国际版" maxLength={100} /></label>
            <div className="research-section">
              <div className="research-heading"><strong>联网物理规格</strong>
                <button type="button" className="research-command" disabled={searching || !brand.trim() || !model.trim()}
                  onClick={() => { void searchSpecs(!!currentResearch); }}>
                  {searching ? <LoaderCircle size={15} className="spin" /> : currentResearch ? <RefreshCw size={15} /> : <Search size={15} />}
                  {searching ? "搜索中" : currentResearch ? "重新搜索" : "搜索规格"}</button></div>
              <p className="research-state" role="status">{startingResearch ? "正在启动联网搜索" : searching ?
                `正在搜索 ${research?.request.brand || brand} ${research?.request.model || model}` : spec ?
                `${spec.model} · ${spec.variant}${currentResearch?.cached ? " · 已缓存" : ""}` : currentResearch?.status === "needs_clarification" ?
                "请明确车型代际或版本" : currentResearch?.status === "not_found" ? "未找到完整的基础尺寸" :
                currentResearch?.status === "failed" || currentResearch?.status === "interrupted" ? "规格检索未完成" : "等待车型规格"}</p>
              {currentResearch?.questions?.map((question, index) => <p key={index} className="constraint blocked">{question}</p>)}
              {(researchError || currentResearch?.error) && <p className="error" role="alert">{researchError || currentResearch?.error}</p>}
              {spec && <>
                <dl className="dimension-grid">{["length", "width", "height", "wheelbase"].map(field => <div key={field}>
                  <dt>{measurementNames[field]}</dt><dd>{spec.measurements[field].value?.toLocaleString()} <small>mm</small></dd></div>)}</dl>
                <details className="spec-details"><summary>物理参数与来源</summary>
                  <table><tbody>{Object.entries(spec.measurements).map(([field, item]) => <tr key={field}>
                    <th>{measurementNames[field] || field}</th><td>{item.value === null ? "未找到" : `${item.value} ${item.unit}`}
                      {item.value !== null && item.source && <a href={spec.sources[item.source].url} target="_blank" rel="noreferrer"
                        title={`${spec.sources[item.source].title}\n${item.evidence}\n${item.note}`} aria-label={`${measurementNames[field]}来源`}><ExternalLink size={12} /></a>}</td></tr>)}</tbody></table>
                  <ol className="source-list">{Object.entries(spec.sources).map(([id, source]) => <li key={id}>
                    <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                    <small>{source.kind === "reference" ? "资料来源" : source.kind === "tyre_manufacturer" ? "轮胎厂商" : "汽车厂商"}</small></li>)}</ol>
                </details>
              </>}
              {currentResearch?.notes?.map((note, index) => <p key={index} className="research-note">{note}</p>)}
            </div>
            <label className="field"><span>模型比例</span><select aria-label="模型比例" value={scale} onChange={e => setScale(e.target.value)}>
              {config?.scales.map(item => <option key={item.scale} value={item.scale}>{item.scale}{item.scale !== "1:24" ? "（仅要求规划）" : ""}</option>)}
              <option value="custom">自定义车长（研究草稿）</option>
            </select></label>
            {scale === "custom" ? <>
              <label className="field"><span>车长 / studs</span><input type="number" aria-label="车长" min={23} max={32} required value={length} onChange={e => setLength(Number(e.target.value))} /></label>
            </> : <div className="scale-requirements"><p>{scaleDescriptions[scale]}</p>
              {policy && <span>{policy.required_measurements.length} 项尺寸资料 · 每步最多 {policy.max_parts_per_step} 件</span>}
            </div>}
            <p className={blocked ? "constraint blocked" : "constraint"}>{!spec ? "等待联网规格" : planError || (currentPlan ?
              currentPlan.generation.draft_recipe_available ? `尺寸辅助 · ${currentPlan.grid.length_studs} × ${currentPlan.grid.width_studs} studs · ${currentPlan.missing_measurements.length} 项所需参数未找到` :
              `当前配方不支持 ${currentPlan.policy.scale} / ${currentPlan.grid.length_studs} × ${currentPlan.grid.width_studs} studs` : "正在规划尺寸")}</p>
            <div className="color-field"><span>车身颜色</span><div role="group" aria-label="车身颜色" className="swatches">
              {config?.colors.map(item => <button key={item.code} type="button" className="swatch" style={{ background: swatches[item.code] }}
                title={item.name} aria-label={item.name} aria-pressed={color === item.code} onClick={() => setColor(item.code)} />)}
            </div></div>
            <label className="field"><span>补充描述（可选）</span><input aria-label="补充描述" value={description} onChange={e => setDescription(e.target.value)} maxLength={100} /></label>
            <label className="field"><span>随机种子</span><input type="number" aria-label="随机种子" min={0} max={4294967295} required value={seed} onChange={e => setSeed(Number(e.target.value))} /></label>
          </fieldset>
          <button className="primary-button" type="submit" disabled={busy || blocked || !config}>
            {busy ? <LoaderCircle size={18} className="spin" /> : <Box size={18} />}{busy ? "正在生成" : "生成研究草稿"}<ArrowRight size={17} />
          </button>
          {error && <p className="error" role="alert">{error}</p>}
        </form>
      </section>
      <section className="result" aria-labelledby="result-title">
        <div className="section-heading"><h2 id="result-title">{job ? `${job.request.brand_zh} ${job.request.model}` : "Ferrari F40"}</h2>
          <span className={`job-status ${job?.status || ""}`} role="status">{job ? statusNames[job.status] : "已有研究草稿"}</span></div>
        <div className="pipeline-strip"><span className={job?.files.image ? "done" : ""}><Image size={16} />参考图片</span><ArrowRight size={14} />
          <span className={job?.files.mesh ? "done" : ""}><Box size={16} />3D 网格</span><ArrowRight size={14} />
          <span className={job?.files.studio ? "done" : ""}><Blocks size={16} />Studio 文件</span></div>
        <figure className="preview">
          <img src={job?.files.preview || job?.files.image || "/api/preview"} alt={job?.files.preview ? "本次重建网格" : job?.files.image ? "本次生成参考图片" : "已有 F40 乐高研究草稿的原生零件渲染"} />
          <figcaption>{job ? (job.files.preview ? "本次重建网格" : job.files.image ? "本次参考图片" : "已有 F40 草稿 · 等待本次结果") : "原生 LEGO 零件渲染 · 外观未验收"}</figcaption>
        </figure>
        {job?.files.studio && <div className="downloads"><a className="primary-button" href={job.files.studio}><Download size={17} />Studio .io</a>
          {[['ldraw', 'LDraw'], ['mesh', '3D 网格'], ['specs', '物理规格'], ['request', '生成参数']].map(([key, label]) => job.files[key] && <a key={key} href={job.files[key]}><Download size={15} />{label}</a>)}</div>}
        {job && <div className="run-details">
          {job.error && <p className="error" role="alert">{job.error}</p>}
          <details open={job.status === "failed"}><summary>运行记录</summary><pre>{job.log || "任务已提交"}</pre></details>
          <p className="constraint">研究草稿；Studio 打开、实体拼装和外观交付均未验收。</p>
        </div>}
      </section>
    </main>
  </>;
}

createRoot(document.getElementById("root")!).render(<App />);
