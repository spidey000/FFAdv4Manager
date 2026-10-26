import React from 'react'
import { createRoot } from 'react-dom/client'
import Demo from './Demo.jsx'
import './styles.css'

class InterfaceBoundary extends React.Component {
  state = { error: null }

  static getDerivedStateFromError(error) { return { error } }

  componentDidCatch(error, info) {
    console.error('Error while rendering Three Slicer', error, info.componentStack)
  }

  render() {
    if (this.state.error) return <main className="startup-error" role="alert">
      <h1>Unable to display the application</h1>
      <p>Reload the page. If the problem persists, copy the error from your browser's developer console for troubleshooting.</p>
      <code>{this.state.error.message}</code>
      <button type="button" onClick={() => window.location.reload()}>Reload</button>
    </main>
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(<React.StrictMode><InterfaceBoundary><Demo /></InterfaceBoundary></React.StrictMode>)
