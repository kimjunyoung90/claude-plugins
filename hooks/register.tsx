import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, RenderSurface } from 'claude-code'

import type { TodoItem, TodoSnapshot } from '../types'
import { ageDays, ageTone, goalItems, isoWeek, parseTodoFile, todayString } from './format'

const PANE = 'todo'
const REFRESH_MS = 60_000

const snapshot = atom({ plugin: 'todo', key: 'snapshot' } as const, {
  items: [],
  today: todayString(),
  week: isoWeek(todayString()),
  updatedAt: '',
} as TodoSnapshot)

// 방향키로 고른 할 일. 줄마다 그린 Button(key row:<id>)에 포커스가 오면 바뀐다
const selected = atom({ plugin: 'todo', key: 'selected' } as const, null as string | null)
const ROW = 'row:'
const STATE = 'state:'  // 줄마다 제목 오른쪽의 상태 셀렉트 — → 로 들어가 Enter 로 고른다
// 셀렉트는 사람이 고른 값을 다시 그려도 붙들고 있다. 고를 때마다 이 번호를 올려 key 를 바꾸면 새로 그린다
const picks = atom({ plugin: 'todo', key: 'picks' } as const, 0)
const PICKED_BG = '#3a3a3a'  // 고른 줄 바탕 — 어두운 패널 위에서 한 단계 밝게

const STATE_OPTIONS = [
  { value: 'todo', label: '할 일' },
  { value: 'in_progress', label: '작업 중' },
  { value: 'done', label: '완료' },
] as const

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

// 화면에 그리는 순서 — 목표 묶음 먼저, 그 밖의 할 일은 뒤에. 방향키가 이 순서로 움직인다
function ordered(snap: TodoSnapshot): TodoItem[] {
  const goals = goalItems(snap.items, snap.week ?? isoWeek(snap.today))
  const ids = new Set(goals.map(i => i.id))
  return [...goals, ...snap.items.filter(i => !ids.has(i.id))]
}

// Enter — 고른 할 일의 작업 세션으로 간다. 찾기·Orca 탭 전환은 scripts/goto.py 가 한다
type GotoResult = { action: 'start' | 'orca' | 'bg' | 'none'; no?: number; id?: string }

async function goTo($: EngineInterface, item: TodoItem, surface?: RenderSurface): Promise<void> {
  let out: GotoResult
  try {
    const ran = await $.process.run(['python3', `${$.plugin.root}/scripts/goto.py`, item.id, '--switch'], { timeoutMs: 30_000 })
    out = JSON.parse(ran.stdout.trim().split('\n').pop() || '{}') as GotoResult
  } catch {
    return  // 세션을 찾지 못하면 아무것도 하지 않는다
  }
  // Orca 탭 전환은 goto.py --switch 가 이미 했다. 갈 세션이 없으면(none) 아무것도 하지 않는다
  if (out.action === 'start') await $.prompt.fill({ text: `/start ${out.no}` })
  else if (out.action === 'bg') await $.ui.copy({ text: `claude attach ${out.id}`, surface })
}

// 상태 셀렉트에서 고른 값 — 상태 바꾸기는 세션·워크로그·지라가 함께 움직여야 해서
// 바로 바꾸지 않고 해당 명령을 입력창에 채운다. 실행은 사람이 Enter 로 한다
async function pickState($: EngineInterface, item: TodoItem, value: string): Promise<void> {
  const now = item.inProgress ? 'in_progress' : 'todo'
  if (value === now) return
  if (value === 'in_progress') await $.prompt.fill({ text: `/start ${item.no}` })
  else if (value === 'done') await $.prompt.fill({ text: `/finish ${item.jira ?? ''}`.trim() })
  // 명령은 아직 실행 전이니 셀렉트는 지금 상태로 되돌려 그린다
  await update($, picks, n => n + 1)
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
    await $.ui.open({ id: PANE, title: '할 일 목록', focus: true })  // 열자마자 방향키가 목록을 움직이게
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

  // 포커스가 줄 사이를 옮겨 갈 때 고른 할 일을 기억해 그 줄을 표시한다
  on('ui.focus', { requestId: PANE }, async ($, e, next) => {
    // ← 가 제목에서 엔진 자리(닫기 ✕)로 넘어가지 않게 — 사람의 키로 할 일 밖에 가려 하면 제자리에 둔다
    if (!e.element && e.origin.kind === 'person') return {}
    const el = e.element ?? ''
    // 제목(row:)이든 상태 셀렉트(state:)든 그 줄을 고른 것으로 친다
    const id = el.startsWith(ROW) ? el.slice(ROW.length) : el.startsWith(STATE) ? el.slice(STATE.length).split('#')[0] : null
    await update($, selected, () => id)
    return next(e)
  })

  // 패널에서 방향키는 원래 화면을 한 줄씩 굴린다. 한 줄짜리 키 이동(포인터 없음)은 굴리는 대신
  // 다음·이전 할 일로 포커스를 옮기고 그 줄이 보이게 한다. 휠·페이지 키는 그대로 굴린다
  on('ui.scroll', { requestId: PANE }, async ($, e, next) => {
    if (e.origin.kind !== 'person' || e.pointer || Math.abs(e.by) !== 1) return next(e)
    const ids = ordered(await read($, snapshot)).map(i => i.id)
    const current = await read($, selected)
    const at = current ? ids.indexOf(current) : -1
    const target = ids[Math.min(ids.length - 1, Math.max(0, at + e.by))]
    if (!target) return next(e)
    await $.ui.focus({ requestId: PANE, key: `${ROW}${target}` })
    await $.ui.scroll({ in: PANE, to: { key: `${ROW}${target}` } })
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button, Select } = $.ui.resolve(e)
    const snap = await read($, snapshot)
    const picked = await read($, selected)
    const pickNo = await read($, picks)
    const first = ordered(snap)[0]?.id
    // 받은 지 며칠 — 줄마다 붙는 ● 색과 같은 기준(ageTone). 위쪽 개수가 그 색의 설명을 겸한다
    const tones = snap.items.map(i => ageTone(ageDays(i.created, snap.today)))
    const fresh = tones.filter(t => t === 'success').length
    const aged = tones.filter(t => t === 'warning').length
    const old = tones.filter(t => t === 'error').length
    const doing = snap.items.filter(i => i.inProgress).length
    const week = snap.week ?? isoWeek(snap.today)
    const goals = goalItems(snap.items, week)
    const grouped = new Set(goals.map(i => i.id))
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

    // 줄 앞 ● 색의 설명 겸 개수 — ● <개수> <뜻>
    const Dot = (p: { label: string; value: number; color: string }) => (
      <Text>
        <Text bold color={p.color}>●</Text>
        <Text bold>{` ${p.value}`}</Text>
        <Text dimColor> {p.label}</Text>
      </Text>
    )

    const Item = (p: { item: TodoItem }) => {
      const days = ageDays(p.item.created, snap.today)
      const tone = ageTone(days)
      // 고른 줄 표시는 키보드가 화면에 있을 때만 — Esc 등으로 입력창에 돌아가면 지운다
      const isPicked = e.props.isFocused && picked === p.item.id
      return (
        // 고른 줄은 왼쪽 막대와 바탕색으로 두 줄(제목·티켓)을 한 덩어리로 드러낸다
        <Box key={p.item.id} flexDirection="column" marginBottom={1} backgroundColor={isPicked ? PICKED_BG : undefined}>
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Box flexDirection="row" gap={1} flexShrink={1}>
              <Text bold color="claude">{isPicked ? '▌' : ' '}</Text>
              <Text bold color="claude">{String(p.item.no).padStart(2, ' ')}</Text>
              {/* 받은 지 며칠은 기호 하나(●)의 색으로만 — 초록 오늘 · 기본 3일 미만 · 노랑 3일↑ · 빨강 7일↑ */}
              <Text color={tone} bold>●</Text>
              {/* 제목을 Button 으로 그려야 포커스가 줄마다 멈춘다. Enter 는 그 할 일의 작업 세션으로 간다 */}
              <Button key={`${ROW}${p.item.id}`} plain label={p.item.title} autoFocus={p.item.id === first ? true : undefined}
                onPress={press => void goTo($, p.item, press.surface)} />
            </Box>
            <Box flexDirection="row" gap={1} flexShrink={0}>
              {/* 상태 셀렉트 — 작업 중이면 「할 일」로 되돌리는 길은 두지 않는다(세션이 이미 떠 있다) */}
              <Select key={`${STATE}${p.item.id}#${pickNo}`} value={p.item.inProgress ? 'in_progress' : 'todo'}
                options={p.item.inProgress ? STATE_OPTIONS.slice(1) : STATE_OPTIONS}
                onSelect={value => void pickState($, p.item, value)} />
            </Box>
          </Box>
          {p.item.jira && (
            <Box flexDirection="row" gap={1}>
              <Text bold color="claude">{isPicked ? '▌' : ' '}</Text>
              <Box paddingLeft={5}>
                <Text dimColor={!isPicked} color={isPicked ? 'claude' : undefined}>{p.item.jira}</Text>
              </Box>
            </Box>
          )}
        </Box>
      )
    }

    return (
      <Box flexDirection="column" width={width} minHeight={rows}>
        <Box flexDirection="row" justifyContent="space-between" gap={2}>
          <Box flexDirection="row" gap={2}>
            {Stat({ label: '할 일', value: snap.items.length, color: 'claude' })}
            {Stat({ label: '작업 중', value: doing, color: 'claude' })}
          </Box>
          <Box flexDirection="row" gap={2}>
            {Dot({ label: '오늘', value: fresh, color: 'success' })}
            {Dot({ label: '3일↑', value: aged, color: 'warning' })}
            {old > 0 && Dot({ label: '7일↑', value: old, color: 'error' })}
          </Box>
        </Box>
        <Text dimColor>{'─'.repeat(width)}</Text>

        {snap.items.length === 0 && !snap.error && <Text color="success">할 일이 없습니다.</Text>}

        {/* 이번 주 목표는 이름 없이 한 묶음. 지난 주 목표인데 안 끝난 건(이월)도 따로 표시 없이 여기 둔다 */}
        {goals.length > 0 && (
          <Box flexDirection="column" marginTop={1}>
            <Text bold color="warning">★ 이번 주 목표</Text>
            {goals.map(item => Item({ item }))}
          </Box>
        )}
        {/* 목표와 나머지 할 일 사이는 이름 없이 선으로만 나눈다 */}
        {goals.length > 0 && rest.length > 0 && <Text dimColor>{'─'.repeat(width)}</Text>}

        <Box flexDirection="column" marginTop={1}>
          {rest.map(item => Item({ item }))}
        </Box>

        <Box flexGrow={1} />
        <Text dimColor>{'─'.repeat(width)}</Text>
        {snap.error ? (
          <Text dimColor wrap="truncate-end">{`갱신 실패: ${snap.error}`}</Text>
        ) : (
          <Box flexDirection="row" justifyContent="space-between" gap={1}>
            <Text dimColor wrap="truncate-end">↑↓ 이동 · Esc 입력창</Text>
            <Text dimColor>{`LastUpdated ${snap.updatedAt}`}</Text>
          </Box>
        )}
      </Box>
    )
  })
}
