import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import Splash from './components/Splash'
import { AuthProvider, ThemeProvider, ToastProvider } from './contexts/AppContexts'
import '@fontsource-variable/inter'
import '@fontsource-variable/playfair-display'
import './styles/index.css'

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider><ToastProvider><AuthProvider><App /><Splash /></AuthProvider></ToastProvider></ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
