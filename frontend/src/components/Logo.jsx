export default function Logo({ className = "" }) {
  return (
    <img
      className={`as-logo-mark ${className}`}
      src="/images/astrosentinel-mark.svg"
      alt=""
      aria-hidden="true"
      width="40"
      height="40"
    />
  );
}
