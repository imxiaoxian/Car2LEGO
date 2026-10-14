import catalog from "@/lib/data/vehicle-brands.json";

export interface VehicleBrand {
  id: string;
  name: string;
  name_zh: string;
  aliases: string[];
  logo: string;
  popular_rank: number | null;
}

export const vehicleBrands: VehicleBrand[] = catalog.brands;
export const popularBrands = vehicleBrands.filter(brand => brand.popular_rank !== null)
  .sort((a, b) => a.popular_rank! - b.popular_rank!);

export function normalizeBrand(value: string) {
  return value.normalize("NFKC").toLocaleLowerCase().replace(/[\s\p{P}\p{S}]/gu, "");
}

export function findVehicleBrand(value: string): VehicleBrand | undefined {
  const key = normalizeBrand(value);
  if (!key) return undefined;
  return vehicleBrands.find(brand => [brand.id, brand.name, brand.name_zh, ...brand.aliases]
    .some(name => normalizeBrand(name) === key));
}

export function searchVehicleBrands(query: string): VehicleBrand[] {
  const key = normalizeBrand(query);
  return vehicleBrands.filter(brand => [brand.id, brand.name, brand.name_zh, ...brand.aliases]
    .some(name => normalizeBrand(name).includes(key)));
}
