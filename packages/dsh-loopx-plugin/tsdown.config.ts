import { defineConfig } from 'tsdown'

export default defineConfig({
  name: 'dsh-loopx-plugin/host',
  entry: {
    index: 'build-temp/host/index.js',
    'init-command': 'build-temp/host/init-command.js',
    driver: 'build-temp/host/driver.js',
    observer: 'build-temp/host/observer.js',
  },
  outDir: 'lib',
  format: ['esm'],
  platform: 'node',
  target: 'es2024',
  fixedExtension: false,
  dts: false,
  clean: false,
  sourcemap: false,
})
