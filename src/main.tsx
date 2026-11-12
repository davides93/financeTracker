import { initializeStorage } from './vaultStorage'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const root = createRoot(document.getElementById('root')!)
initializeStorage().then(() => root.render(
  <StrictMode>
    <App />
  </StrictMode>,
)).catch(() => root.render(<p role="alert">Impossibile aprire l’archivio locale. Chiudi e riapri l’app. Nessun dato è stato sostituito.</p>))
