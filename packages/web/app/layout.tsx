import type { Metadata, Viewport } from "next";
// MapLibre CSS first so the app styles (Tailwind utilities on the map container) win.
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "LITHOS: See the ground move",
  description:
    "Free, open ground-motion intelligence. Watch the Earth's surface rise and sink, millimetre by millimetre, and get an automatic flag when something is wrong. Measured from Sentinel-1 by way of COMET LiCSAR.",
  metadataBase: new URL("https://lithos.northflow.no"),
  openGraph: {
    title: "LITHOS: See the ground move",
    description: "Open ground-motion intelligence. Type a place. See whether it is moving.",
    type: "website",
  },
  twitter: { card: "summary_large_image", title: "LITHOS: See the ground move" },
};

export const viewport: Viewport = {
  themeColor: "#0b0e12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
