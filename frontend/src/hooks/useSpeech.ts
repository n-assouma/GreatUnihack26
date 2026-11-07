import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../api'

// The Web Speech API is not in every TypeScript DOM lib, so describe the small part we use.
interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface RecognitionEvent { resultIndex: number; results: ArrayLike<RecognitionResult> }
interface Recognition {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number
  start(): void; stop(): void; abort(): void
  onresult: ((e: RecognitionEvent) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognitionCtor = new () => Recognition

const ctor = (): RecognitionCtor | undefined => {
  const w = window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition
}

export type VoiceEngine = 'elevenlabs' | 'browser'

const ERROR_TEXT: Record<string, string> = {
  'not-allowed': 'The microphone is blocked. Allow it in your browser settings, then try again.',
  'service-not-allowed': 'The microphone is blocked. Allow it in your browser settings, then try again.',
  'no-speech': "I didn't hear anything. Tap the mic and try again.",
  'audio-capture': 'No microphone was found.',
  network: 'Speech recognition needs an internet connection.',
}

interface Options {
  /** Called with the final words once the person stops talking. */
  onFinal: (text: string) => void
  /** Speaking speed, 1 = normal. Applied as the playback rate, so it works for ElevenLabs and the browser voice alike. */
  rate?: number
}

/**
 * Voice in and out. In: browser speech recognition (en-GB). Out: POST /api/tts (ElevenLabs on the backend),
 * and if that is unavailable (503, no key, offline) the browser's own voice. The app works without any of it.
 */
export function useSpeech({ onFinal, rate = 1 }: Options) {
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [engine, setEngine] = useState<VoiceEngine | null>(null)

  const recognition = useRef<Recognition | null>(null)
  const audio = useRef<HTMLAudioElement | null>(null)
  const audioUrl = useRef<string | null>(null)
  const run = useRef(0) // bumped on every speak() / cancel() so a late response cannot play over a newer one
  const onFinalRef = useRef(onFinal)
  onFinalRef.current = onFinal
  const rateRef = useRef(rate)
  rateRef.current = rate

  const supported = typeof window !== 'undefined' && Boolean(ctor())

  const stopPlayback = useCallback(() => {
    if (audio.current) { audio.current.onended = null; audio.current.onerror = null; audio.current.pause(); audio.current = null }
    if (audioUrl.current) { URL.revokeObjectURL(audioUrl.current); audioUrl.current = null }
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  }, [])

  const cancel = useCallback(() => {
    run.current += 1
    stopPlayback()
    setSpeaking(false)
  }, [stopPlayback])

  const speak = useCallback(async (text: string) => {
    const id = ++run.current
    stopPlayback()
    setSpeaking(true)
    const finish = () => { if (id === run.current) { stopPlayback(); setSpeaking(false) } }

    const blob = await api.tts(text)
    if (id !== run.current) return // Stop was pressed, or a newer message started

    if (blob) {
      const url = URL.createObjectURL(blob)
      audioUrl.current = url
      const el = new Audio(url)
      el.playbackRate = rateRef.current // pitch is preserved by default, so faster does not sound squeaky
      audio.current = el
      el.onended = finish
      el.onerror = finish
      try {
        await el.play()
        setEngine('elevenlabs')
        return
      } catch {
        // Autoplay blocked or the file would not decode: try the browser voice instead.
        stopPlayback()
      }
    }

    if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(text)
      u.lang = 'en-GB'
      u.rate = rateRef.current
      const voice = window.speechSynthesis.getVoices().find((v) => v.lang === 'en-GB')
      if (voice) u.voice = voice
      u.onend = finish
      u.onerror = finish
      setEngine('browser')
      window.speechSynthesis.speak(u)
    } else {
      finish()
    }
  }, [stopPlayback])

  const start = useCallback(() => {
    const Ctor = ctor()
    if (!Ctor) return
    cancel() // never listen while speaking: the microphone would hear the app
    const r = new Ctor()
    r.lang = 'en-GB'
    r.interimResults = true
    r.continuous = false
    r.maxAlternatives = 1
    let finalText = ''
    r.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) finalText += res[0].transcript
        else interim += res[0].transcript
      }
      setTranscript((finalText + interim).trim())
    }
    r.onerror = (e) => setError(ERROR_TEXT[e.error] ?? 'Speech recognition stopped unexpectedly.')
    r.onend = () => {
      recognition.current = null
      setListening(false)
      setTranscript('')
      const text = finalText.trim()
      if (text) onFinalRef.current(text)
    }
    recognition.current = r
    setError(null)
    setListening(true)
    try {
      r.start()
    } catch {
      recognition.current = null
      setListening(false)
    }
  }, [cancel])

  const stop = useCallback(() => { recognition.current?.stop() }, [])

  useEffect(() => () => {
    recognition.current?.abort()
    run.current += 1
    stopPlayback()
  }, [stopPlayback])

  return { supported, listening, speaking, transcript, error, engine, start, stop, speak, cancel }
}
