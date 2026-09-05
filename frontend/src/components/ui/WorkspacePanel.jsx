import { cn } from '../../lib/utils.js'

export default function WorkspacePanel({ as: Element = 'section', className, children, ...props }) {
  return <Element className={cn('workspace-panel', className)} {...props}>{children}</Element>
}
