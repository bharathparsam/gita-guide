import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Gita Guide",
    short_name: "Gita Guide",
    description: "Grounded reflections from the Bhagavad Gita for life's difficult moments.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#f7f6f0",
    theme_color: "#315c48",
    orientation: "any",
    categories: ["lifestyle", "education"],
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
