import { useState } from "react";

import { formatLongDateTime } from "../cases/format";
import type { RectificationEvidence } from "../cases/types";

interface RectificationEvidenceGalleryProps {
  evidence: RectificationEvidence[];
}

export function RectificationEvidenceGallery({ evidence }: RectificationEvidenceGalleryProps) {
  return (
    <div className="rectification-evidence-gallery">
      {evidence.map((item, index) => (
        <RectificationEvidenceImage
          key={item.evidence_id}
          evidence={item}
          index={index}
        />
      ))}
    </div>
  );
}

function RectificationEvidenceImage({
  evidence,
  index,
}: {
  evidence: RectificationEvidence;
  index: number;
}) {
  const [failed, setFailed] = useState(false);
  const label = evidence.note?.trim() || `整改证据 ${index + 1}`;

  return (
    <figure className="rectification-evidence-image">
      {failed ? (
        <div className="rectification-evidence-image__error" role="alert">
          <span>整改图片加载失败</span>
          <button type="button" onClick={() => setFailed(false)}>重新加载</button>
        </div>
      ) : (
        <img src={evidence.image_url} alt={label} onError={() => setFailed(true)} />
      )}
      <figcaption>
        <strong>{label}</strong>
        <time dateTime={evidence.captured_at}>{formatLongDateTime(evidence.captured_at)}</time>
        <a href={evidence.image_url} target="_blank" rel="noreferrer">查看原图</a>
      </figcaption>
    </figure>
  );
}
