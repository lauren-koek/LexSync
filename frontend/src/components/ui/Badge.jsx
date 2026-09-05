import { cn } from '../../lib/utils.js'

const TONES = {
  neutral: 'bg-panel text-ink-soft border-border',
  sage: 'bg-decision-green-bg text-decision-green border-transparent',
  red: 'bg-decision-red-bg text-decision-red border-transparent',
  amber:
    'bg-decision-amber-bg text-decision-amber border-transparent',
}

export default function Badge({ tone = 'neutral', className, ...props }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-none',
        TONES[tone],
        className,
      )}
      {...props}
    />
  )
}
