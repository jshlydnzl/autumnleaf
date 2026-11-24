import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

function App() {
  const [status, setStatus] = useState('Checking')

  useEffect(() => {
    const controller = new AbortController()

    async function checkApi() {
      try {
        const response = await fetch('/api/health/', { signal: controller.signal })
        if (!response.ok || (await response.json()).status !== 'ok') {
          throw new Error('API unavailable')
        }
        if (!controller.signal.aborted) setStatus('Online')
      } catch {
        if (!controller.signal.aborted) setStatus('Unavailable')
      }
    }

    void checkApi()
    return () => controller.abort()
  }, [])

  return (
    <main className="grid min-h-screen place-items-center bg-zinc-950 px-6 text-zinc-100">
      <section className="w-full max-w-xl rounded-xl border border-zinc-800 bg-zinc-900 p-8">
        <h1 className="text-4xl font-semibold tracking-tight text-orange-300">AutumnLeaf</h1>
        <p className="mt-3 text-zinc-300">A personal data warehouse workbench.</p>
        <p className="mt-6 text-sm text-zinc-300" role="status">
          Django API: <strong className="text-zinc-100">{status}</strong>
        </p>
      </section>
    </main>
  )
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing application root')
createRoot(root).render(<StrictMode><App /></StrictMode>)
