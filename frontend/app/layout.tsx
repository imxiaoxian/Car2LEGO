import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Car2LEGO — Turn Any Car into LEGO",
  description:
    "Input any car make, model and year. Get LEGO building instructions, parts list, and BrickLink shopping list.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
            <a href="/" className="flex items-center gap-2">
              <span className="text-2xl">🧱</span>
              <span className="font-bold text-xl tracking-tight">
                Car<span className="text-brick-red">2</span>LEGO
              </span>
            </a>
            <nav className="flex gap-6 text-sm font-medium text-gray-600">
              <a href="/" className="hover:text-gray-900 transition-colors">
                Home
              </a>
              <a
                href="/sets"
                className="hover:text-gray-900 transition-colors"
              >
                Browse
              </a>
            </nav>
          </div>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="bg-white border-t border-gray-200 py-8 text-center text-sm text-gray-500">
          <p>
            Car2LEGO — LEGO® is a trademark of the LEGO Group. Not affiliated.
          </p>
        </footer>
      </body>
    </html>
  );
}
