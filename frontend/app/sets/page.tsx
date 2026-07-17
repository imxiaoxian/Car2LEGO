"use client";

import { useEffect, useState } from "react";
import { getKnownCars, LegoSetInfo } from "@/lib/api";

export default function BrowsePage() {
  const [sets, setSets] = useState<LegoSetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    getKnownCars()
      .then(setSets)
      .finally(() => setLoading(false));
  }, []);

  const filtered = filter
    ? sets.filter(
        (s) =>
          s.car_make?.toLowerCase().includes(filter.toLowerCase()) ||
          s.car_model?.toLowerCase().includes(filter.toLowerCase()) ||
          s.set_num.toLowerCase().includes(filter.toLowerCase())
      )
    : sets;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-extrabold mb-2">Browse Known LEGO Cars</h1>
      <p className="text-gray-600 mb-8">
        {sets.length} official LEGO car sets in the database — click any to get
        a design.
      </p>

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter by make, model, or set number..."
        className="w-full border border-gray-300 rounded-xl px-4 py-3 mb-6 focus:ring-2 focus:ring-brick-red focus:border-transparent outline-none"
      />

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((s) => (
            <a
              key={s.set_num}
              href={`/designs/${s.set_num}`}
              className="block bg-white border border-gray-200 rounded-xl p-4 hover:border-brick-red hover:shadow-md transition"
            >
              <div className="font-semibold text-lg">
                {s.car_make} {s.car_model}
              </div>
              <div className="text-sm text-gray-500 mt-1">{s.name}</div>
              <div className="flex items-center justify-between mt-3 text-sm text-gray-400">
                <span>Set {s.set_num}</span>
                <span>{s.brick_count} pieces</span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
