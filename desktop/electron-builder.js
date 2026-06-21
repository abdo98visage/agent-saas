const updateFeedUrl = process.env.UPDATE_FEED_URL || "";

const config = {
  appId: "com.fqsaas.desktop",
  productName: "FQ-SaaS Workspace",
  directories: {
    output: "dist",
    buildResources: "build",
  },
  files: [
    "src/**/*",
    "desktop-config.json",
    "package.json",
  ],
  artifactName: "${productName}-${version}-${arch}.${ext}",
  win: {
    target: [
      {
        target: "nsis",
        arch: ["x64"],
      },
    ],
    verifyUpdateCodeSignature: true,
  },
  nsis: {
    oneClick: false,
    perMachine: true,
    allowToChangeInstallationDirectory: true,
    artifactName: "${productName}-Setup-${version}.${ext}",
  },
};

if (updateFeedUrl) {
  config.publish = [
    {
      provider: "generic",
      url: updateFeedUrl,
    },
  ];
}

module.exports = config;
