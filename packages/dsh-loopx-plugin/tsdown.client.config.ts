import { existsSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import { isBuiltin } from 'node:module'
import { basename, dirname, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { transform } from 'lightningcss'
import { defineConfig } from 'tsdown'

const PACKAGE_ID = 'dsh-loopx-plugin'
const PACKAGE_ROOT = fileURLToPath(new URL('.', import.meta.url))
const CLIENT_OUTPUT_MARKER = `${sep}build-temp${sep}client${sep}`
const CSS_VIRTUAL_PREFIX = '\0loopx-css:'
const CSS_VIRTUAL_SUFFIX = '.mjs'

/** Runtime identities supplied by DSH's frozen browser module table. */
const SHARED_BROWSER_RUNTIME = new Set([
  'react',
  'react/jsx-runtime',
  'react-dom',
  'react-dom/client',
  '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-primitives',
  '@deepseek-ai/dsh-client-ui-renderer/client',
  '@deepseek-ai/dsh-client-ui-slots',
])

function sourceAssetPath(source: string, importer: string): string {
  const emitted = resolve(dirname(importer), source)
  if (existsSync(emitted)) return emitted
  const boundary = emitted.indexOf(CLIENT_OUTPUT_MARKER)
  if (boundary < 0) return emitted
  return resolve(
    emitted.slice(0, boundary),
    'src',
    emitted.slice(boundary + CLIENT_OUTPUT_MARKER.length),
  )
}

function packageRelative(file: string): string {
  const path = relative(PACKAGE_ROOT, file)
  if (path === '..' || path.startsWith(`..${sep}`)) {
    throw new Error('client CSS must stay inside dsh-loopx-plugin')
  }
  return path.split(sep).join('/')
}

function styleInjectionModule(
  relativeFile: string,
  css: string,
  classMap: Readonly<Record<string, string>>,
): string {
  return [
    `const css = ${JSON.stringify(css)};`,
    `const tagId = ${JSON.stringify(`${PACKAGE_ID}/${basename(relativeFile)}`)};`,
    'function ensurePluginStyle() {',
    "  if (typeof document === 'undefined' || document.querySelector('style[data-plugin-css=' + JSON.stringify(tagId) + ']') !== null) return;",
    "  const tag = document.createElement('style');",
    `  tag.dataset.plugin = ${JSON.stringify(PACKAGE_ID)};`,
    '  tag.dataset.pluginCss = tagId;',
    '  tag.textContent = css;',
    '  document.head.appendChild(tag);',
    '}',
    'ensurePluginStyle();',
    'export { ensurePluginStyle };',
    `export default ${JSON.stringify(classMap)};`,
  ].join('\n')
}

export default defineConfig({
  name: `${PACKAGE_ID}/client`,
  entry: { client: 'build-temp/client/client/index.js' },
  outDir: 'lib',
  format: 'cjs',
  platform: 'browser',
  target: 'es2024',
  dts: false,
  clean: false,
  sourcemap: false,
  deps: {
    neverBundle: (specifier: string) => SHARED_BROWSER_RUNTIME.has(specifier),
    alwaysBundle: (specifier: string) =>
      !isBuiltin(specifier) && !SHARED_BROWSER_RUNTIME.has(specifier),
  },
  plugins: [
    {
      name: 'loopx-client-bundle-purity',
      resolveId(source: string) {
        if (isBuiltin(source)) {
          throw new Error(`client bundle purity: Node builtin ${JSON.stringify(source)} is forbidden`)
        }
        if (source.startsWith('@deepseek-ai/') && !SHARED_BROWSER_RUNTIME.has(source)) {
          throw new Error(
            `client bundle purity: ${JSON.stringify(source)} is not an approved DSH browser runtime identity`,
          )
        }
        return null
      },
    },
    {
      name: 'loopx-css-modules-inline',
      resolveId(source: string, importer: string | undefined) {
        if (!source.endsWith('.module.css') || importer === undefined) return null
        const relativeFile = packageRelative(sourceAssetPath(source, importer))
        return `${CSS_VIRTUAL_PREFIX}${relativeFile}${CSS_VIRTUAL_SUFFIX}`
      },
      async load(virtualId: string) {
        if (!virtualId.startsWith(CSS_VIRTUAL_PREFIX)) return null
        const relativeFile = virtualId.slice(
          CSS_VIRTUAL_PREFIX.length,
          -CSS_VIRTUAL_SUFFIX.length,
        )
        const fileId = resolve(PACKAGE_ROOT, relativeFile)
        this.addWatchFile(fileId)
        const source = await readFile(fileId)
        const result = transform({
          filename: relativeFile,
          code: source,
          cssModules: { pattern: '[hash]_[local]' },
          minify: true,
        })
        const classMap: Record<string, string> = {}
        for (const [local, value] of Object.entries(result.exports ?? {}).sort()) {
          classMap[local] = value.name
        }
        return styleInjectionModule(relativeFile, result.code.toString(), classMap)
      },
    },
  ],
  outputOptions: {
    entryFileNames: 'client.js',
    banner: `window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE_ID)}, factory: (require) => {`,
    footer: 'return module.exports; } });',
    intro: 'var module = { exports: {} }; var exports = module.exports;',
  },
})
