/**
 * Chat Store
 *
 * Manages chat messages with aggregation by utterance ID for LLM streaming.
 * Handles STT, LLM, TTS, and Memory message updates.
 *
 * @module stores/chat
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '../types/ui'
import {
  isSTTFinalMessage,
  isSTTPartialMessage,
  isLLMStreamMessage,
  isLLMResponseMessage,
  isTTSSayMessage,
  isTTSStatusMessage,
  isMemoryResultsMessage,
  type MemoryResultsMessage
} from '../types/mqtt'

export const useChatStore = defineStore('chat', () => {
  // State
  const messages = ref<ChatMessage[]>([])
  const partialText = ref('')
  const assistantMessages = ref<Map<string, ChatMessage>>(new Map())
  const lastMemory = ref<MemoryResultsMessage | null>(null)

  // Actions
  function addMessage(message: Omit<ChatMessage, 'timestamp'>): void {
    const newMessage: ChatMessage = {
      ...message,
      timestamp: Date.now()
    }
    messages.value.push(newMessage)
  }

  function addUserMessage(text: string): void {
    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      text,
      meta: 'You'
    })
  }

  function ensureAssistantMessage(
    id: string,
    options: { meta?: string; reset?: boolean } = {}
  ): ChatMessage {
    const key = id || 'default'
    let message = assistantMessages.value.get(key)

    if (!message) {
      message = {
        id: key,
        role: 'tars',
        text: '',
        meta: options.meta ?? 'TARS',
        timestamp: Date.now(),
        streaming: false,
        lastSeq: 0,
        ttsChunks: 0
      }
      assistantMessages.value.set(key, message)
      messages.value.push(message)
    }

    if (options.reset) {
      message.text = ''
      message.lastSeq = 0
      message.ttsChunks = 0
      message.streaming = false
    }

    return message
  }

  function setAssistantText(
    id: string,
    text: string,
    options: { meta?: string; reset?: boolean } = {}
  ): void {
    const message = ensureAssistantMessage(id, options)
    message.text = text || ''
    message.ttsChunks = 0
  }

  function joinParts(prev: string, next: string): string {
    const a = (prev || '').trimEnd()
    const b = (next || '').trimStart()

    if (!a) return b
    if (!b) return a

    const needSpace = !/[\s]$/.test(a) && !/^[\s.,!?;:]/.test(b)
    return a + (needSpace ? ' ' : '') + b
  }

  // Message Handlers
  function handleSTTMessage(topic: string, payload: unknown): void {
    if (topic.endsWith('stt/partial') && isSTTPartialMessage(payload)) {
      partialText.value = payload.text || ''
    } else if (topic.endsWith('stt/final') && isSTTFinalMessage(payload)) {
      partialText.value = ''
      if (payload.text) {
        addUserMessage(payload.text)
      }
    }
  }

  function handleLLMMessage(topic: string, payload: unknown): void {
    if (topic.endsWith('llm/stream') && isLLMStreamMessage(payload)) {
      const data = payload.data
      const id = data.id || 'default'
      const seq = typeof data.seq === 'number' ? data.seq : null

      const message = ensureAssistantMessage(id, {
        meta: 'TARS',
        reset: seq !== null && seq <= 1
      })

      if (data.delta) {
        message.text = message.text ? message.text + data.delta : data.delta
      }

      if (seq !== null) {
        message.lastSeq = seq
      }

      message.streaming = !data.done
      message.ttsChunks = 0
    } else if (topic.endsWith('llm/response') && isLLMResponseMessage(payload)) {
      const data = payload.data
      const id = data.id || 'default'
      const finalText = (data.reply || '').trim()

      if (finalText) {
        setAssistantText(id, finalText, { meta: 'TARS' })
      }

      const message = assistantMessages.value.get(id)
      if (message) {
        message.streaming = false
      }
    }
  }

  function handleTTSMessage(topic: string, payload: unknown): void {
    if (topic.endsWith('tts/say') && isTTSSayMessage(payload)) {
      const id = payload.utt_id || 'default'
      const chunk = (payload.text || '').trim()

      if (chunk) {
        const message = ensureAssistantMessage(id, {
          meta: payload.wake_ack ? 'TARS' : 'TARS'
        })

        // Only aggregate if no LLM stream (for wake acknowledgments)
        if (!message.lastSeq || message.lastSeq === 0) {
          message.ttsChunks = (message.ttsChunks ?? 0) + 1
          message.text = message.ttsChunks === 1 ? chunk : joinParts(message.text, chunk)
        }
      }
    } else if (topic.endsWith('tts/status') && isTTSStatusMessage(payload)) {
      // Status updates handled by app state, not chat messages
    }
  }

  function handleMemoryMessage(topic: string, payload: unknown): void {
    if (topic.endsWith('memory/results') && isMemoryResultsMessage(payload)) {
      lastMemory.value = payload
    }
  }

  return {
    // State
    messages,
    partialText,
    lastMemory,

    // Actions
    addMessage,
    addUserMessage,
    handleSTTMessage,
    handleLLMMessage,
    handleTTSMessage,
    handleMemoryMessage
  }
})
