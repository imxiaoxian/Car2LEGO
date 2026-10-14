import { useEffect, useState, FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, Blocks, Box, Download, Image, LoaderCircle } from "lucide-react";
import BrandSelector from "@/components/BrandSelector";
import { vehicleBrands } from "@/lib/vehicle-brands";
import "./styles.css";

interface Policy { scale: string; required_measurements: string[]; max_parts_per_step: number }
interface Config { scales: Policy[]; colors: { code: number; name: string }[] }
interface Job {
  id: string; status: string; error: string | null; files: Record<string, string>; log: string;
  request: { brand_zh: string; model: string; scale: string };
}
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
  const hasSpec = !custom && brand === "Ferrari" && model.trim().toLowerCase() === "f40";
  const policy = config?.scales.find(item => item.scale === scale);
  const blocked = scale !== "custom" && (!hasSpec || scale !== "1:24");

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
        body: JSON.stringify({ brand, custom, model, scale, length_studs: length, color, seed, description }) });
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
              if (isCustom !== custom || (!isCustom && value !== brand)) { setModel(""); setScale("custom"); }
              setBrand(value); setCustom(isCustom); setError("");
            }} />
            <label className="field"><span>车型</span><input aria-label="车型" value={model} onChange={e => setModel(e.target.value)}
              placeholder="F40" required maxLength={64} /></label>
            <label className="field"><span>模型比例</span><select aria-label="模型比例" value={scale} onChange={e => setScale(e.target.value)}>
              {config?.scales.map(item => <option key={item.scale} value={item.scale}>{item.scale}{item.scale !== "1:24" ? "（仅要求规划）" : ""}</option>)}
              <option value="custom">自定义车长（研究草稿）</option>
            </select></label>
            {scale === "custom" ? <>
              <label className="field"><span>车长 / studs</span><input type="number" aria-label="车长" min={23} max={32} required value={length} onChange={e => setLength(Number(e.target.value))} /></label>
              <p className="constraint">通用跑车配方；未采用该车型的物理规格，实际比例未验证。</p>
            </> : <div className="scale-requirements"><p>{scaleDescriptions[scale]}</p>
              {policy && <span>{policy.required_measurements.length} 项尺寸资料 · 每步最多 {policy.max_parts_per_step} 件</span>}
              <p className={blocked ? "constraint blocked" : "constraint"}>{!hasSpec ? "该车型尚无已核对的物理规格。" : scale !== "1:24" ? "独立配方尚未实现。" : "Ferrari F40 原厂尺寸辅助；机构和外观尚未验收。"}</p>
            </div>}
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
          {[['ldraw', 'LDraw'], ['mesh', '3D 网格'], ['request', '生成参数']].map(([key, label]) => job.files[key] && <a key={key} href={job.files[key]}><Download size={15} />{label}</a>)}</div>}
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
