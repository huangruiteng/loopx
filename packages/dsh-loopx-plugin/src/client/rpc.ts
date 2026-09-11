import type { ClientConnectionRpc } from '@deepseek-ai/dsh-client-connection/client'

import {
  GOALBAR_REQUEST_VERSION,
  decodeGoalBarResponseV1,
  endpointForGoalBarOp,
} from '../goalbar/protocol.ts'
import type {
  GoalBarClientFaultCode,
  GoalBarAgentStatusV1,
  GoalBarExpectedBindingV1,
  GoalBarRequestV1,
  GoalBarResponseFor,
} from '../goalbar/protocol.ts'

const GOALBAR_CHANNEL = '/loopx'
const GOALBAR_SHARED_API_CHANNEL = '/api'
const GOALBAR_SHARED_API_ENDPOINT = 'loopx.goalbar'

export type GoalBarRpcOutcome<T> =
  | { readonly ok: true; readonly response: T }
  | { readonly ok: false; readonly code: GoalBarClientFaultCode }

export type GoalBarReadResponseV1 = GoalBarResponseFor<Extract<
  GoalBarRequestV1,
  { readonly op: 'read' }
>>

export type GoalBarWatchResponseV1 = GoalBarResponseFor<Extract<
  GoalBarRequestV1,
  { readonly op: 'watch' }
>>

export type GoalBarStartResponseV1 = GoalBarResponseFor<Extract<
  GoalBarRequestV1,
  { readonly op: 'start' }
>>

export type GoalBarPauseResponseV1 = GoalBarResponseFor<Extract<
  GoalBarRequestV1,
  { readonly op: 'pause' }
>>

export interface GoalBarWatchAnchorV1 {
  readonly afterSessionEventSeq: number | null
  readonly sourceRevision: string
  readonly expected: GoalBarExpectedBindingV1 | null
  readonly agentStatus: GoalBarAgentStatusV1 | null
}

/** The four browser operations consumed by one mounted GoalBar instance. */
export interface GoalBarRpc {
  read(
    sessionId: string,
    signal: AbortSignal,
  ): Promise<GoalBarRpcOutcome<GoalBarReadResponseV1>>
  watch(
    sessionId: string,
    anchor: GoalBarWatchAnchorV1,
    signal: AbortSignal,
  ): Promise<GoalBarRpcOutcome<GoalBarWatchResponseV1>>
  start(
    sessionId: string,
    expected: GoalBarExpectedBindingV1,
    signal: AbortSignal,
  ): Promise<GoalBarRpcOutcome<GoalBarStartResponseV1>>
  pause(
    sessionId: string,
    expected: GoalBarExpectedBindingV1,
    signal: AbortSignal,
  ): Promise<GoalBarRpcOutcome<GoalBarPauseResponseV1>>
}

type ConnectionRpcCaller = Pick<ClientConnectionRpc, 'call'>

async function callGoalBar<T extends GoalBarRequestV1>(
  caller: ConnectionRpcCaller,
  request: T,
  signal: AbortSignal,
  sharedApi: boolean,
): Promise<GoalBarRpcOutcome<GoalBarResponseFor<T>>> {
  try {
    const endpoint = endpointForGoalBarOp(request.op)
    const carrier = await caller.call(
      sharedApi ? GOALBAR_SHARED_API_CHANNEL : GOALBAR_CHANNEL,
      sharedApi ? GOALBAR_SHARED_API_ENDPOINT : endpoint,
      request,
      signal,
    )
    if (!carrier.ok) return { ok: false, code: 'transport_error' }
    const response = decodeGoalBarResponseV1(request, carrier.value)
    return response === undefined
      ? { ok: false, code: 'protocol_error' }
      : { ok: true, response }
  } catch {
    return { ok: false, code: 'transport_error' }
  }
}

/**
 * Wrap DSH's generic Connection caller with the closed GoalBar V2 wire.
 * Carrier errors and thrown values are deliberately discarded at this boundary.
 */
export function createGoalBarRpc(
  caller: ConnectionRpcCaller,
  sharedApi = false,
): GoalBarRpc {
  return {
    read(sessionId, signal) {
      const request = {
        v: GOALBAR_REQUEST_VERSION,
        op: 'read',
        sessionId,
      } as const
      return callGoalBar(caller, request, signal, sharedApi)
    },
    watch(sessionId, anchor, signal) {
      const request = {
        v: GOALBAR_REQUEST_VERSION,
        op: 'watch',
        sessionId,
        ...anchor,
      } as const
      return callGoalBar(caller, request, signal, sharedApi)
    },
    start(sessionId, expected, signal) {
      const request = {
        v: GOALBAR_REQUEST_VERSION,
        op: 'start',
        sessionId,
        expected,
      } as const
      return callGoalBar(caller, request, signal, sharedApi)
    },
    pause(sessionId, expected, signal) {
      const request = {
        v: GOALBAR_REQUEST_VERSION,
        op: 'pause',
        sessionId,
        expected,
      } as const
      return callGoalBar(caller, request, signal, sharedApi)
    },
  }
}
