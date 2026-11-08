/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    VARYNX_API_URL: process.env.VARYNX_API_URL || "http://localhost:8000/api/v1",
  },
};

module.exports = nextConfig;