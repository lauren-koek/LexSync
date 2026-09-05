const TOKEN_PATTERN = /(\[-[\s\S]*?-\]|\{\+[\s\S]*?\+\})/g

export default function Redline({ value }) {
  return (
    <div className="whitespace-pre-wrap rounded-lg border border-border bg-canvas p-3 text-[13px] leading-relaxed">
      {value.split(TOKEN_PATTERN).filter(Boolean).map((part, index) => {
        if (part.startsWith('[-'))
          return (
            <del
              key={index}
              className="bg-decision-red-bg text-decision-red no-underline line-through"
            >
              {part.slice(2, -2)}
            </del>
          )
        if (part.startsWith('{+'))
          return (
            <ins
              key={index}
              className="bg-decision-green-bg text-decision-green no-underline"
            >
              {part.slice(2, -2)}
            </ins>
          )
        return <span key={index}>{part}</span>
      })}
    </div>
  )
}
