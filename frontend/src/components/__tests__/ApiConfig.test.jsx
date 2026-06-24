test("uses env variable when set (process.env fallback)", async () => {
  // Ensure process.env is set before importing the module
  process.env.VITE_API_URL = 'https://test.api';
  const mod = await import('../../config');
  expect(mod.default).toBe('https://test.api');
});

test("falls back to /api when no env set", async () => {
  // Clear possible env and re-import
  delete process.env.VITE_API_URL;
  const mod = await import('../../config');
  expect(mod.default).toBe('/api');
});
