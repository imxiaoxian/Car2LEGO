/** API client for the Car2LEGO backend. */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export interface CarResult {
  id: string;
  make: string;
  model: string;
  year: number;
  trim?: string;
  body_style?: string;
  image_url?: string;
  created_at: string;
}

export interface MatchInfo {
  level: number;
  label: string;
  confidence: number;
  set_num?: string;
  set_name?: string;
  moc_name?: string;
  moc_author?: string;
}

export interface DesignPart {
  part_num: string;
  ldraw_color_id: number;
  color_name?: string;
  quantity: number;
  bricklink_id?: string;
  name?: string;
  image_url?: string;
}

export interface Design {
  id: string;
  car_id?: string;
  match?: MatchInfo;
  status: string;
  parts_count?: number;
  difficulty?: string;
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface DesignDetail extends Design {
  car?: CarResult;
  parts: DesignPart[];
  file_urls: Record<string, string>;
  parent_design_id?: string;
  customization_request?: string;
}

export interface CustomizationResponse {
  id: string;
  status: string;
  message: string;
  parent_design_id: string;
}

export interface DesignStatus {
  id: string;
  status: string;
  progress: number;
  stage?: string;
  error_message?: string;
}

export interface LegoSetInfo {
  set_num: string;
  name: string;
  year?: number;
  brick_count?: number;
  car_make?: string;
  car_model?: string;
  image_url?: string;
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  return res.json();
}

/** POST /designs — submit a car and get a LEGO design */
export async function createDesign(
  make: string,
  model: string,
  year: number,
  image_url?: string
): Promise<DesignDetail> {
  return fetchApi<DesignDetail>("/designs", {
    method: "POST",
    body: JSON.stringify({ make, model, year, image_url }),
  });
}

/** GET /designs/:id */
export async function getDesign(id: string): Promise<DesignDetail> {
  return fetchApi<DesignDetail>(`/designs/${id}`);
}

/** GET /designs/:id/status */
export async function getDesignStatus(id: string): Promise<DesignStatus> {
  return fetchApi<DesignStatus>(`/designs/${id}/status`);
}

/** GET /designs/:id/parts */
export async function getDesignParts(id: string): Promise<DesignPart[]> {
  return fetchApi<DesignPart[]>(`/designs/${id}/parts`);
}

/** GET /sets/known-cars */
export async function getKnownCars(): Promise<LegoSetInfo[]> {
  return fetchApi<LegoSetInfo[]>("/sets/known-cars");
}

/** GET /sets */
export async function searchSets(
  make?: string,
  model?: string
): Promise<LegoSetInfo[]> {
  const params = new URLSearchParams();
  if (make) params.set("make", make);
  if (model) params.set("model", model);
  return fetchApi<LegoSetInfo[]>(`/sets?${params.toString()}`);
}

/** GET /cars/lookup */
export async function lookupCar(make: string, model: string, year: number) {
  return fetchApi<CarResult>("/cars/lookup", {
    method: "POST",
    body: JSON.stringify({ make, model, year }),
  });
}

/** POST /designs/:id/customize — customize an existing design */
export async function customizeDesign(
  designId: string,
  customizationText: string
): Promise<CustomizationResponse> {
  return fetchApi<CustomizationResponse>(`/designs/${designId}/customize`, {
    method: "POST",
    body: JSON.stringify({ customization_text: customizationText }),
  });
}

/** GET /designs/:id/ldr — get raw LDraw content for 3D viewer */
export async function getDesignLdr(id: string): Promise<string> {
  const url = `${API_URL}/designs/${id}/ldr`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load LDraw: ${res.status}`);
  return res.text();
}

/** POST /designs/:id/studio-open — open design in BrickLink Studio */
export async function openInStudio(designId: string): Promise<{
  success: boolean;
  io_path: string;
  studio_opened: boolean;
  file_opened: boolean;
}> {
  return fetchApi(`/designs/${designId}/studio-open`, { method: "POST" });
}

/** GET /mods — get all modification parts catalog */
export interface ModPartInfo {
  id: string;
  name: string;
  category: string;
  real_world_ref: string;
  description: string;
  difficulty: string;
  estimated_parts: number;
  visual_change: string;
  lego_parts_count: number;
}

export async function getModsCatalog(): Promise<Record<string, ModPartInfo[]>> {
  return fetchApi<Record<string, ModPartInfo[]>>("/mods");
}
