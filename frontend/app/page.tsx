"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { createDesign, getKnownCars, LegoSetInfo } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [knownCars, setKnownCars] = useState<LegoSetInfo[]>([]);
  const [showKnown, setShowKnown] = useState(false);

  const loadKnownCars = useCallback(async () => {
    if (knownCars.length > 0) {
      setShowKnown(!showKnown);
      return;
    }
    try {
      const cars = await getKnownCars();
      setKnownCars(cars);
      setShowKnown(true);
    } catch {
      // silently fail
    }
  }, [knownCars, showKnown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!make.trim() || !model.trim() || !year.trim()) {
      setError("Please fill in all fields.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const design = await createDesign(
        make.trim(),
        model.trim(),
        parseInt(year)
      );
      router.push(`/designs/${design.id}`);
    } catch (err: any) {
      setError(err.message || "Something went wrong. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-16">
      {/* Hero */}
      <div className="text-center mb-12">
        <h1 className="text-5xl font-extrabold tracking-tight mb-4">
          Turn Any Car into{" "}
          <span className="brick-gradient bg-clip-text text-transparent">
            LEGO
          </span>
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Enter any car model from around the world — get LEGO building
          instructions, parts lists, and a BrickLink shopping list.
        </p>
      </div>

      {/* Search Form */}
      <form
        onSubmit={handleSubmit}
        className="bg-white rounded-2xl shadow-lg p-8 mb-8"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Make (Brand)
            </label>
            <input
              type="text"
              value={make}
              onChange={(e) => setMake(e.target.value)}
              placeholder="e.g., Porsche, Toyota, Ferrari"
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-brick-red focus:border-transparent outline-none transition"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model
            </label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g., 911, Supra, F40"
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-brick-red focus:border-transparent outline-none transition"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Year
            </label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="e.g., 2020"
              min={1900}
              max={2030}
              className="w-full border border-gray-300 rounded-lg px-4 py-3 text-lg focus:ring-2 focus:ring-brick-red focus:border-transparent outline-none transition"
            />
          </div>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 rounded-lg px-4 py-3 mb-4 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-brick-red hover:bg-red-700 text-white font-bold py-4 px-8 rounded-xl text-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Spinner />
              Matching your car...
            </span>
          ) : (
            "🔍 Find LEGO Design"
          )}
        </button>
      </form>

      {/* Quick examples */}
      <div className="text-center mb-8">
        <button
          onClick={loadKnownCars}
          className="text-sm text-gray-500 hover:text-gray-700 underline underline-offset-4"
        >
          {showKnown ? "Hide known models" : "Browse known LEGO car models →"}
        </button>
      </div>

      {showKnown && knownCars.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {knownCars
            .filter((s) => s.car_make && s.car_model)
            .slice(0, 40)
            .map((s) => (
              <button
                key={s.set_num}
                onClick={async () => {
                  setMake(s.car_make || "");
                  setModel(s.car_model || "");
                  setYear(s.year?.toString() || "");
                  try {
                    setLoading(true);
                    const design = await createDesign(
                      s.car_make!,
                      s.car_model!,
                      s.year || 2020
                    );
                    router.push(`/designs/${design.id}`);
                  } catch {
                    setLoading(false);
                  }
                }}
                className="bg-white border border-gray-200 rounded-xl p-3 text-left hover:border-brick-red hover:shadow-md transition text-sm"
              >
                <div className="font-semibold text-gray-900 truncate">
                  {s.car_make} {s.car_model}
                </div>
                <div className="text-gray-500 text-xs mt-1">{s.name}</div>
                <div className="text-gray-400 text-xs">
                  {s.brick_count} pieces • Set {s.set_num}
                </div>
              </button>
            ))}
        </div>
      )}

      {/* How it works */}
      <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-6">
        <StepCard
          emoji="🚗"
          title="1. Enter Your Car"
          description="Type in any car make, model, and year from around the world."
        />
        <StepCard
          emoji="🧱"
          title="2. Get LEGO Design"
          description="We match against official LEGO sets, community MOCs, or generate a custom design."
        />
        <StepCard
          emoji="🛒"
          title="3. Buy & Build"
          description="Download the parts list, buy on BrickLink, and start building!"
        />
      </div>
    </div>
  );
}

function StepCard({
  emoji,
  title,
  description,
}: {
  emoji: string;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center p-6">
      <div className="text-4xl mb-3">{emoji}</div>
      <h3 className="font-bold text-lg mb-2">{title}</h3>
      <p className="text-gray-600 text-sm">{description}</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="animate-spin h-5 w-5"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
