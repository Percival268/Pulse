const Card = ({ children, className = "" }) => (
  <div className={`rounded-xl border p-4 shadow ${className}`}>{children}</div>
);
export default Card;
