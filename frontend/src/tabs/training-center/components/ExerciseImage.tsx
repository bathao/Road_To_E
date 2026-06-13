import { useState } from "react";
import { poseSvg } from "../constants";

// Resolves an exercise image with graceful fallback:
//   real GIF (/exercises/<key>.gif)  ->  bundled pose SVG  ->  🏋️ placeholder
export default function ExerciseImage({
  gif,
  alt,
  className,
}: {
  gif: string;
  alt: string;
  className: string;
}) {
  const key = gif ? gif.split("/").pop()!.replace(/\.gif$/, "") : "";
  const sources = [gif, key ? poseSvg(key) : ""].filter(Boolean);
  const [i, setI] = useState(0);
  if (i >= sources.length) {
    return <div className={`${className} ${className}-ph`}>🏋️</div>;
  }
  return (
    <img className={className} src={sources[i]} alt={alt} onError={() => setI(i + 1)} />
  );
}
