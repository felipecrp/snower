const target = process.env.SNOW_API_URL || 'http://localhost:8000';

module.exports = {
  '/api': {
    target,
    secure: false,
    changeOrigin: true,
  },
};
