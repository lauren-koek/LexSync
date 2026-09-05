export default function PageIntro({ eyebrow, title, description, status, children }) {
  return (
    <header className="page-intro">
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <div className="page-intro__row">
        <div className="page-intro__copy">
          <h1>{title}</h1>
          {description && <p className="page-intro__description">{description}</p>}
        </div>
        {(status || children) && <div className="page-intro__aside">{status && <p className="page-intro__status">{status}</p>}{children}</div>}
      </div>
    </header>
  )
}
