/** todo.jsonl 의 할 일(todo·in_progress) 한 건 (화면에 필요한 필드만) */
export type TodoItem = {
  /** todo.py todo 와 같은 번호 (추가한 시각 순) */
  no: number
  /** 할 일 id (T-NNNN) */
  id: string
  /** 추가한 시각 YYYY-MM-DDTHH:MM */
  created: string
  title: string
  jira: string | null
  /** state 가 in_progress (/start 로 작업 중) */
  inProgress: boolean
  /** 목표로 정한 ISO 주 (YYYY-Www) · 목표 아니면 null */
  goal: string | null
  /** 목표 이름 — 같은 이름끼리 한 묶음 */
  goalName: string | null
}

/** 화면 맨 위 목표 묶음 하나 */
export type GoalGroup = {
  name: string
  /** 이월이면 원래 주, 이번 주면 null */
  carried: string | null
  items: TodoItem[]
}

export type TodoSnapshot = {
  items: TodoItem[]
  /** 기준일 YYYY-MM-DD (갱신 시점) */
  today: string
  /** 기준 ISO 주 YYYY-Www (갱신 시점) */
  week: string
  /** 마지막 갱신 시각 HH:MM:SS */
  updatedAt: string
  error?: string
}

declare module 'claude-code' {
  interface PluginState {
    'todo': {
      snapshot: TodoSnapshot
      /** 화면에서 방향키로 고른 할 일 id (T-NNNN) · 고르지 않았으면 null */
      selected: string | null
    }
  }
}
