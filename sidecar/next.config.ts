import type { NextConfig } from "next";

const config: NextConfig = {
  experimental: {
    serverActions: {
      allowedOrigins: ["southbrookcabinetry.space"],
    },
  },
};

export default config;
