import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { TodoItem, TodoSnapshot } from '../types'
import { ageDays, ageLabel, ageTone, goalGroups, isoWeek, parseTodoFile, todayString } from './format'

const PANE = 'todo'
const REFRESH_MS = 60_000

const snapshot = atom({ plugin: 'todo', key: 'snapshot' } as const, {
  items: [],
  today: todayString(),
  week: isoWeek(todayString()),
  updatedAt: '',
} as TodoSnapshot)

function clock(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

// 할 일 목록은 $TODO_DATA_DIR/todo.jsonl — 스크립트(todo.py)와 같은 환경변수, 없으면 ~/.claude/todo
async function ledgerPath($: EngineInterface): Promise<string> {
  const home = (await $.env.get('HOME')) ?? ''
  const dir = (await $.env.get('TODO_DATA_DIR')) || `${home}/.claude/todo`
  return `${dir.startsWith('~/') ? `${home}${dir.slice(1)}` : dir}/todo.jsonl`
}

async function refresh($: EngineInterface): Promise<void> {
  try {
    const text = await $.fs.read(await ledgerPath($))
    const items = parseTodoFile(text)
    const today = todayString()
    await update($, snapshot, () => ({ items, today, week: isoWeek(today), updatedAt: clock() }))
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    await update($, snapshot, prev => ({ ...prev, updatedAt: clock(), error: message }))
  }
}

export const register: Register = on => {

  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'todo', description: '할 일 목록 화면 열기' })
    void refresh($)
    $.clock.every(REFRESH_MS, () => void refresh($))
    return next(e)
  })

  on('command.run', { command: 'todo' }, async $ => {
    await $.ui.open({ id: PANE, title: '할 일 목록' })
    await refresh($)
    const { items } = await read($, snapshot)
    return { text: `할 일 목록 화면을 열었습니다 (할 일 ${items.length}건).` }
  })

  // 원장을 바꾸는 Bash 실행 뒤에는 바로 갱신한다
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    try {
      if (/todo\.py/.test(e.command)) void refresh($).catch(() => {})
    } catch {
      // 갱신 실패가 Bash 실행 결과를 막지 않게 한다
    }
    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const snap = await read($, snapshot)
    const stale = snap.items.filter(i => ageDays(i.created, snap.today) >= 7).length
    const fresh = snap.items.filter(i => i.created.slice(0, 10) === snap.today).length
    const doing = snap.items.filter(i => i.inProgress).length
    const week = snap.week ?? isoWeek(snap.today)
    const groups = goalGroups(snap.items, week)
    const grouped = new Set(groups.flatMap(g => g.items.map(i => i.id)))
    const rest = snap.items.filter(i => !grouped.has(i.id))
    // pane 본문 폭 기준. 오른쪽 끝 한 칸은 엔진의 스크롤 표시와 겹쳐 잘리므로 2칸 비운다
    const width = Math.max(20, (e.props.bodyColumns ?? 60) - 2)
    // 목록이 짧아도 범례가 pane 맨 아래에 붙도록 본문 높이만큼 채운다
    const rows = Math.max(8, e.props.scroll?.bodyRows ?? 0)

    const Stat = (p: { label: string; value: number; color: string }) => (
      <Text>
        <Text bold color={p.color}>{String(p.value)}</Text>
        <Text dimColor> {p.label}</Text>
      </Text>
    )

    const Item = (p: { item: TodoItem }) => {
      const days = ageDays(p.item.created, snap.today)
      const tone = ageTone(days)
      return (
        <Box key={p.item.id} flexDirection="column" marginBottom={1}>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Box flexDirection="row" gap={1} flexShrink={1}>
              <Text bold color="claude">{String(p.item.no).padStart(2, ' ')}</Text>
              <Text color={tone} bold>{days >= 7 ? '●' : days === 0 ? '✦' : '○'}</Text>
              <Text bold wrap="truncate-end">{p.item.title}</Text>
            </Box>
            <Box flexDirection="row" gap={1} flexShrink={0}>
              {p.item.inProgress && (
                <Text backgroundColor="claude" color="inverseText" bold>{' 작업 중 '}</Text>
              )}
              <Text color={tone} bold={tone !== 'text'}>{ageLabel(days)}</Text>
            </Box>
          </Box>
          {p.item.jira && (
            <Box paddingLeft={5}>
              <Text dimColor>{p.item.jira}</Text>
            </Box>
          )}
        </Box>
      )
    }

    return (
      <Box flexDirection="column" width={width} minHeight={rows}>
        <Box flexDirection="row" gap={2} flexWrap="wrap">
          {Stat({ label: '할 일', value: snap.items.length, color: 'claude' })}
          {Stat({ label: '작업 중', value: doing, color: 'claude' })}
          {Stat({ label: '오늘', value: fresh, color: 'success' })}
          {Stat({ label: '7일↑', value: stale, color: stale > 0 ? 'error' : 'subtle' })}
        </Box>
        <Text dimColor>{'─'.repeat(width)}</Text>

        {snap.items.length === 0 && !snap.error && <Text color="success">할 일이 없습니다.</Text>}

        {groups.map(g => (
          <Box key={`${g.name}@${g.carried ?? week}`} flexDirection="column" marginTop={1}>
            <Text bold color="warning" wrap="truncate-end">
              {`★ ${g.name}`}
              {g.carried ? <Text dimColor>{` (이월 ${g.carried})`}</Text> : null}
            </Text>
            {g.items.map(item => Item({ item }))}
          </Box>
        ))}
        {groups.length > 0 && rest.length > 0 && <Text dimColor>{'── 그 외'}</Text>}

        <Box flexDirection="column" marginTop={1}>
          {rest.map(item => Item({ item }))}
        </Box>

        <Box flexGrow={1} />
        <Text dimColor>{'─'.repeat(width)}</Text>
        <Text dimColor wrap="truncate-end">
          {snap.error
            ? `갱신 실패: ${snap.error}`
            : `✦ 오늘  ○ 7일 미만  ● 7일↑  ★ 목표 · 갱신 ${snap.updatedAt}`}
        </Text>
      </Box>
    )
  })
}
