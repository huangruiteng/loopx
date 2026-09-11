import type { Context } from '@deepseek-ai/cordis'
import type { ConnectionHandle } from '@deepseek-ai/dsh-client-connection/client'
import type {} from '@deepseek-ai/dsh-client-locale/client'
import type {} from '@deepseek-ai/dsh-client-runtime/client'
import type {} from '@deepseek-ai/dsh-client-ui-conversation/client'

import { LoopXGoalBar } from './LoopXGoalBar.tsx'
import { ensurePluginStyle } from './goalbar.module.css'
import {
  GOALBAR_LOCALES,
  GOALBAR_LOCALE_NAMESPACE,
} from './locale.ts'
import { createGoalBarRpc } from './rpc.ts'

const PACKAGE_ID = 'dsh-loopx-plugin'

/** Cordis service names required before the materialized Client plugin applies. */
export const inject = ['connection', 'locale', 'slots'] as const

type GoalBarClientContext = Context & {
  readonly connection: ConnectionHandle
}

/** Register the exact-Session LoopX GoalBar contribution and its owned copy. */
export function apply(ctx: GoalBarClientContext): void {
  // Client module exports are cached across a same-page plugin reapply, so CSS
  // installation must be an explicit, idempotent apply-time operation.
  ensurePluginStyle()

  // Register ownership immediately after installation, before any later apply
  // step can fail, so Cordis rollback and ordinary unload both remove the tag.
  ctx.effect(() => () => {
    if (typeof document === 'undefined') return
    for (const style of document.querySelectorAll('style[data-plugin]')) {
      if (style.getAttribute('data-plugin') === PACKAGE_ID) style.remove()
    }
  }, 'dsh-loopx-plugin CSS ownership')

  ctx.effect(
    () => ctx.locale.register(GOALBAR_LOCALE_NAMESPACE, GOALBAR_LOCALES),
    'dsh-loopx-plugin GoalBar locale',
  )

  const rpc = createGoalBarRpc(
    ctx.connection.rpc,
    Reflect.has(ctx.connection, 'generation'),
  )
  ctx.slots.inject('conversation.input.dock', () => ctx.slots.register({
    name: 'conversation.input.dock',
    id: 'loopx-goal',
    order: 15,
    locale: GOALBAR_LOCALE_NAMESPACE,
    inject: sessionId => ({
      rpcSessionId: String(sessionId),
      rpc,
      subscribeConnectionReset: (listener: () => void) => (
        ctx.on('connection/reset', listener)
      ),
    }),
  }, LoopXGoalBar))
}
