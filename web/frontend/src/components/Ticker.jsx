export function Ticker({ items }) {
  if (!items || !items.length) return null

  return (
    <div className="ticker" aria-hidden="true">
      <div className="ticker__track">
        {[0, 1].map((copy) => (
          <div className="ticker__group" key={copy}>
            {items.map((item, index) => (
              <span className="ticker__item" key={`${copy}-${index}`}>
                <span className="ticker__dot" />
                {item.label}
                <strong>{item.value}</strong>
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
