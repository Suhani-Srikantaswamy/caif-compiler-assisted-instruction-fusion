import { Component, type ReactNode } from 'react'

/** Keeps a crash in one page from blanking the whole app; shows the error instead. */
export class ErrorBoundary extends Component<{ children: ReactNode; resetKey: string }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidUpdate(prev: { resetKey: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-800">
        <div className="font-semibold">This page hit an error while rendering.</div>
        <pre className="mt-2 whitespace-pre-wrap font-mono text-xs">{this.state.error.message}</pre>
        <button className="btn-secondary mt-3" onClick={() => this.setState({ error: null })}>Try again</button>
      </div>
    )
  }
}
