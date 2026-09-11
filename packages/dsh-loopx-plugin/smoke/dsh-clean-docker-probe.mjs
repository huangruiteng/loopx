#!/usr/bin/env node

import { randomUUID } from 'node:crypto'

const [baseUrl, workspace] = process.argv.slice(2)
if (!baseUrl || !workspace) throw new Error('missing DSH base URL or workspace')
const endpoint = new URL(baseUrl)
if (endpoint.protocol !== 'http:' || endpoint.hostname !== '127.0.0.1') {
  throw new Error('DSH smoke endpoint must use container-local loopback')
}

const exchange = await fetch(endpoint, {
  redirect: 'manual',
  signal: AbortSignal.timeout(10_000),
})
if (exchange.status !== 303) {
  throw new Error(`DSH launch-token exchange returned HTTP ${exchange.status}`)
}
const cookie = exchange.headers.get('set-cookie')?.split(';', 1)[0]
if (!cookie) throw new Error('DSH launch-token exchange omitted its session cookie')
const cleanEndpoint = new URL(exchange.headers.get('location') ?? '/', endpoint)

async function rpc(payload) {
  const rpcId = randomUUID()
  const method = 'loopx.goalbar'
  const response = await fetch(new URL(`/api/${method}`, cleanEndpoint), {
    method: 'POST',
    headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify({ type: 'client-request', rpcId, method, payload }),
    signal: AbortSignal.timeout(10_000),
  })
  if (response.status !== 200) {
    throw new Error(`${method} returned HTTP ${response.status}`)
  }
  const body = await response.json()
  if (body.rpcId !== rpcId || body.result?.ok !== true) {
    throw new Error(`${method} failed`)
  }
  return body.result.value
}

const sessionId = 'clean-docker-no-agent'
const result = await rpc({
  v: 'loopx_goalbar_request_v2',
  op: 'read',
  sessionId,
})
if (result.result?.kind !== 'fault' || result.result.code !== 'session_unavailable') {
  throw new Error('DSH 0.1.5 GoalBar shared-API route returned an unexpected result')
}
process.stdout.write(JSON.stringify({
  ok: true,
  sessionId,
  carrier: 'shared-api',
  loopx: true,
}))
