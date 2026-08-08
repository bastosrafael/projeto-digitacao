import { useEffect, useRef, useState } from 'react'

import ChatInput from './components/ChatInput.jsx'
import ChatMessage, { LoadingMessage } from './components/ChatMessage.jsx'
import Header from './components/Header.jsx'
import { getUploadConfig, sendMessage, uploadSpreadsheet } from './services/api.js'

const STORAGE_KEY = 'projeto-digitacao:chat-history:v1'

function createMessageId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function createInitialMessage() {
  return {
    id: createMessageId(),
    role: 'assistant',
    text: 'Olá! Sou seu assistente de produtos. Como posso ajudar hoje?',
    timestamp: new Date().toISOString(),
  }
}

function loadMessages() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return [createInitialMessage()]

    const messages = JSON.parse(stored)
    if (!Array.isArray(messages) || messages.length === 0) {
      return [createInitialMessage()]
    }

    return messages
  } catch (error) {
    console.warn('Não foi possível recuperar o histórico local.', error)
    return [createInitialMessage()]
  }
}

export default function App() {
  const [messages, setMessages] = useState(loadMessages)
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadConfig, setUploadConfig] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    getUploadConfig()
      .then(setUploadConfig)
      .catch((error) => {
        console.error('Não foi possível carregar a configuração de upload.', error)
      })
  }, [])

  async function handleSend(text) {
    if (isLoading) return

    const userMessage = {
      id: createMessageId(),
      role: 'user',
      text,
      timestamp: new Date().toISOString(),
    }

    setMessages((current) => [...current, userMessage])
    setIsLoading(true)

    try {
      const response = await sendMessage(text)
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: 'assistant',
          text: response,
          timestamp: new Date().toISOString(),
        },
      ])
    } catch (error) {
      console.error('Falha ao enviar mensagem para o assistente.', error)
      setMessages((current) => [
        ...current,
        {
          id: createMessageId(),
          role: 'assistant',
          text: 'Não foi possível conectar ao assistente. Tente novamente em alguns instantes.',
          timestamp: new Date().toISOString(),
          isError: true,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  function clearConversation() {
    const initialMessages = [createInitialMessage()]
    setMessages(initialMessages)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(initialMessages))
  }

  async function handleUpload(file) {
    if (isUploading) return null

    setIsUploading(true)
    try {
      return await uploadSpreadsheet(file)
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="app-shell">
      <div className="ambient-shape ambient-shape--one" />
      <div className="ambient-shape ambient-shape--two" />

      <div className="chat-panel">
        <Header onClear={clearConversation} canClear={messages.length > 1 && !isLoading} />

        <main className="chat-main">
          <section className="conversation-intro" aria-labelledby="conversation-title">
            <span className="intro-kicker">Conversa atual</span>
            <h2 id="conversation-title">Como posso ajudar?</h2>
            <p>
              Tire dúvidas, organize informações e prepare seu catálogo com ajuda da IA.
            </p>
          </section>

          <section className="messages" aria-live="polite" aria-busy={isLoading}>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {isLoading && <LoadingMessage />}
            <div ref={messagesEndRef} />
          </section>
        </main>

        <footer className="chat-footer">
          <ChatInput
            onSend={handleSend}
            onUpload={handleUpload}
            isLoading={isLoading}
            isUploading={isUploading}
            uploadConfig={uploadConfig}
          />
          <p className="privacy-note">Sua conversa fica salva somente neste navegador.</p>
        </footer>
      </div>
    </div>
  )
}
