// Typed client for every endpoint in docs/CONTRACTS.md §3.
// With VITE_USE_MOCKS=1, or when a request fails, fixtures from src/mocks are returned instead.
import * as mocks from './mocks'
import type {
  BuildingSummary, ChatResponse, ClientContext, Health, IndoorRoute, LocateResult, SessionInfo, Timetable,
} from './types'

const FORCE_MOCKS = import.meta.env.VITE_USE_MOCKS === '1'

async function request<T>(path: string, init: RequestInit | undefined, fallback: () => T): Promise<T> {
  if (FORCE_MOCKS) return fallback()
  try {
    const res = await fetch(path, init)
    if (!res.ok) throw new Error(`${path} -> ${res.status}`)
    return (await res.json()) as T
  } catch (err) {
    console.warn('API failed, using mock:', err)
    return fallback()
  }
}

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

function mockChat(message: string): ChatResponse {
  const m = message.toLowerCase()
  if (/lost|hurt|help/.test(m)) return mocks.chatEscalation
  if (/east|entrance|ankle|lift|indoor/.test(m)) return mocks.chatIndoor
  return mocks.chatOutdoor
}

export const chat = (session_id: string, message: string, context: ClientContext) =>
  request<ChatResponse>('/api/chat', post({ session_id, message, context }), () => mockChat(message))

export const tick = (session_id: string, context: ClientContext) =>
  request<ChatResponse>('/api/tick', post({ session_id, context }), () => mocks.chatTick)

export const confirmEscalation = (session_id: string, confirm: boolean) =>
  request<ChatResponse>('/api/escalation/confirm', post({ session_id, confirm }), () => ({
    ...mocks.chatEscalation,
    reply: confirm ? 'Reception has been notified. Your last known position is shown below.' : 'Okay, I will not contact reception.',
    ui: { escalation: { ...mocks.escalation, needs_confirmation: false } },
  }))

export const getSession = (session_id: string) =>
  request<SessionInfo>(`/api/session/${session_id}`, undefined, () => ({
    phase: 'idle', agent: 'coordinator', next_class: null, profile: {},
  }))

export const getTimetable = (demo_time?: string | null) =>
  request<Timetable>(
    `/api/timetable${demo_time ? `?demo_time=${encodeURIComponent(demo_time)}` : ''}`, undefined,
    () => ({ classes: [mocks.chatOutdoor.ui.next_class!], next_class: mocks.chatOutdoor.ui.next_class!, now: new Date().toISOString() }),
  )

export const getHealth = () =>
  request<Health>('/api/health', undefined, () => ({
    ok: true, mocks: { llm: true, routes: true, tts: true, indoor: true },
  }))

export const getBuilding = () =>
  request<BuildingSummary>('/api/indoor/building', undefined, () => mocks.buildingSummary)

export const indoorRoute = (start: string, destination: string, accessible: boolean, heading?: number) =>
  request<IndoorRoute>('/api/indoor/route', post({ start, destination, accessible, heading }), () => mocks.indoorRoute)

export const locate = (text: string) =>
  request<LocateResult>('/api/indoor/locate', post({ text }), () => ({
    node_id: 'entrance_east', confidence: 0.9, candidates: [],
  }))

/** POST /api/tts. Returns an mp3 Blob, or null when the backend has no key (503) or is down. */
export async function tts(text: string): Promise<Blob | null> {
  if (FORCE_MOCKS) return null
  try {
    const res = await fetch('/api/tts', post({ text }))
    return res.ok ? await res.blob() : null
  } catch {
    return null
  }
}
