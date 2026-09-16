import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { delimiter, join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { pluginPythonCandidates } from '../src/managed-runtime.ts'

describe('installed Python discovery', () => {
  it('discovers unlisted minors in numeric order without executable suffix lookalikes', async () => {
    const directory = await mkdtemp(join(tmpdir(), 'loopx-python-discovery-'))
    try {
      for (const name of ['python3.9', 'python3.97', 'python3.12', 'python3.999-config']) {
        await writeFile(join(directory, name), '# fixture executable\n')
      }
      await mkdir(join(directory, 'python3.998'))
      expect(pluginPythonCandidates({ env: { PATH: directory } })).toEqual([
        'python3', 'python3.97', 'python3.12', 'python3.9',
      ])
      expect(pluginPythonCandidates({ env: { PATH: `${directory}${delimiter}${directory}` } }))
        .toEqual(['python3', 'python3.97', 'python3.12', 'python3.9'])
    } finally {
      await rm(directory, { recursive: true, force: true })
    }
  })

  it('keeps an explicit interpreter authoritative and tolerates missing PATH directories', () => {
    expect(pluginPythonCandidates({ pythonBin: '/configured/python', env: { PATH: '/missing' } }))
      .toEqual(['/configured/python'])
    expect(pluginPythonCandidates({ env: { PATH: '/missing', PYTHON_BIN: '/custom/python' } }))
      .toEqual(['/custom/python'])
    expect(pluginPythonCandidates({ env: { PATH: '/missing' } })).toEqual(['python3'])
  })
})
