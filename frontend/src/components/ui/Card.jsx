import { cn } from '../../lib/utils.js'

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-card',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('px-5 pt-4', className)} {...props} />
}

export function CardBody({ className, ...props }) {
  return <div className={cn('px-5 py-4', className)} {...props} />
}
