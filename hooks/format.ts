// todo.jsonl 을 읽어 화면용 묶음으로 나눈다. 엔진에 기대지 않는 순수 함수만 둔다.
import type { GoalGroup, TodoItem } from '../types'

export type AgeTone = 'success' | 'text' | 'warning' | 'error'

type Row = Record<string, unknown>

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null)

/** jsonl 텍스트 → 할 일(todo·in_progress) 건만. 깨진 줄은 건너뛴다. */
export function parseTodoFile(text: string): TodoItem[] {
  const items: TodoItem[] = []
  for (const line of text.split('\n')) {
    if (line.trim() === '') continue
    let row: Row
    try {
      row = JSON.parse(line) as Row
    } catch {
      continue
    }
    if (row.state !== 'todo' && row.state !== 'in_progress') continue
    items.push({
      no: 0,
      id: str(row.id) ?? '',
      created: str(row.created) ?? '',
      title: str(row.title) ?? '',
      jira: str(row.jira),
      inProgress: row.state === 'in_progress',
      goal: str(row.goal),
      goalName: str(row.goal_name),
    })
  }
  // todo.py todo 와 같은 순서(접수 시각, 같으면 할 일 id 순)로 번호를 매긴다
  return items.sort((a, b) => a.created.localeCompare(b.created) || a.id.localeCompare(b.id)).map((item, i) => ({ ...item, no: i + 1 }))
}

/** YYYY-MM-DD → ISO 주 YYYY-Www. todo.py 의 date.isocalendar() 와 같은 값 */
export function isoWeek(day: string): string {
  const d = new Date(`${day}T00:00:00Z`)
  const dow = d.getUTCDay() || 7
  d.setUTCDate(d.getUTCDate() + 4 - dow) // 그 주의 목요일이 속한 해가 ISO 연도다
  const year = d.getUTCFullYear()
  const week = Math.ceil(((d.getTime() - Date.UTC(year, 0, 1)) / 86_400_000 + 1) / 7)
  return `${year}-W${String(week).padStart(2, '0')}`
}

/** 이번 주 목표이거나 이월 — 미래 주 목표는 아직 아니다. todo.py is_goal 과 같은 기준 */
export function isGoal(item: TodoItem, week: string): boolean {
  return item.goal !== null && item.goal <= week
}

/** 목표별 묶음 — todo.py goal_groups 와 같은 기준. 목록 번호 순으로 처음 나온 묶음부터 */
export function goalGroups(items: TodoItem[], week: string): GoalGroup[] {
  const groups = new Map<string, GoalGroup>()
  for (const item of items) {
    if (!isGoal(item, week)) continue
    const name = item.goalName ?? ''
    const id = `${name}\u0000${item.goal}`
    if (!groups.has(id)) groups.set(id, { name, carried: item.goal === week ? null : item.goal, items: [] })
    groups.get(id)!.items.push(item)
  }
  return [...groups.values()]
}

/** 추가한 날(created)부터 기준일까지 경과 일수 */
export function ageDays(created: string, today: string): number {
  const a = Date.parse(`${created.slice(0, 10)}T00:00:00Z`)
  const b = Date.parse(`${today}T00:00:00Z`)
  if (Number.isNaN(a) || Number.isNaN(b)) return 0
  return Math.max(0, Math.round((b - a) / 86_400_000))
}

export function ageTone(days: number): AgeTone {
  if (days === 0) return 'success'
  if (days >= 14) return 'error'
  if (days >= 7) return 'warning'
  return 'text'
}

export function todayString(d = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
