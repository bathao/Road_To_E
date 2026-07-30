// Segmented button group — the app's standard exclusive-choice control.
// One place owns the "seg / seg-btn active" markup that used to be
// copy-pasted per filter row.
export default function Seg<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: [T, string][];
  value: T;
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div className={`seg${className ? ` ${className}` : ""}`}>
      {options.map(([k, lbl]) => (
        <button
          key={k}
          className={`seg-btn${value === k ? " active" : ""}`}
          onClick={() => onChange(k)}
        >
          {lbl}
        </button>
      ))}
    </div>
  );
}
