import { cn } from '../../lib/utils.js'

export default function MetricStrip({ items, className }) {
  return (
    <div className={cn('metric-strip', className)} role="group" aria-label="Summary metrics">
      {items.map(item => (
        <div className="metric-strip__item" key={item.label}>
          <span className="eyebrow">{item.label}</span>
          <strong className={cn('metric-strip__value metric-value', item.tone && `metric-strip__value--${item.tone}`)}>{item.value}</strong>
        </div>
      ))}
    </div>
  )
}
