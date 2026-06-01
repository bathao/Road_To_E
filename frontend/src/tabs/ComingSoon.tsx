export default function ComingSoon({ label }: { label: string }) {
  return (
    <div className="coming-soon">
      <div className="coming-soon-icon">🚧</div>
      <h2>{label}</h2>
      <p>This tab is coming soon.</p>
    </div>
  );
}
