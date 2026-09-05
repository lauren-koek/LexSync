import { cn } from '../../lib/utils.js'

const VARIANTS = {
  primary:
    'bg-ink text-white hover:bg-accent-ink disabled:opacity-50',
  secondary:
    'bg-white text-ink border border-border hover:border-border-strong hover:bg-panel disabled:opacity-50',
  ghost:
    'bg-transparent text-ink-soft hover:bg-panel disabled:opacity-50',
}

const SIZES = {
  sm: 'h-8 px-3 text-[13px]',
  md: 'h-9 px-4 text-sm',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  className,
  ...props
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    />
  )
}
