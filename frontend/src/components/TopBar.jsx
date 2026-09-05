export default function TopBar({ days, onDaysChange, onFetch, loading }) {
  return (
    <header className="topbar">
      <span className="updates-label">MAS regulatory feed</span>
      <label>
        Last
        <input
          type="number"
          min="1"
          max="365"
          value={days}
          onChange={e => onDaysChange(Number(e.target.value))}
          disabled={loading}
        />
        days
      </label>
      <button className="fetch-btn" onClick={onFetch} disabled={loading}>
        {loading && <span className="spinner" />}
        {loading ? 'Fetching…' : 'Fetch Latest Updates'}
      </button>
    </header>
  )
}
