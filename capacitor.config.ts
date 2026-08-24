import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.tatameone.app',
  appName: 'TatameOne',
  webDir: 'public',
  server: {
    url: 'https://tatameone-api-1.onrender.com',
    cleartext: false
  }
};

export default config;
