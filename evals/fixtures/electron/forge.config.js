module.exports = {
  packagerConfig: { asar: true },
  makers: [
    { name: '@electron-forge/maker-zip', platforms: ['darwin'] },
    { name: '@electron-forge/maker-deb', config: {} },
  ],
};
