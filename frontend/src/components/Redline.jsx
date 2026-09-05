const TOKEN_PATTERN = /(\[-[\s\S]*?-\]|\{\+[\s\S]*?\+\})/g

export default function Redline({ value }) {
  return (
    <div className="redline">
      {value.split(TOKEN_PATTERN).filter(Boolean).map((part, index) => {
        if (part.startsWith('[-')) return <del key={index}>{part.slice(2, -2)}</del>
        if (part.startsWith('{+')) return <ins key={index}>{part.slice(2, -2)}</ins>
        return <span key={index}>{part}</span>
      })}
    </div>
  )
}
