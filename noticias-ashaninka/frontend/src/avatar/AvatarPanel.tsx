// Componente Preact del avatar: listo para integrarse en la PWA de la Fase 4 (condición C4).
import { useEffect, useRef } from "preact/hooks";
import { createAvatar, type AvatarHandle } from "./create-avatar";
import type { DegradationEvent } from "./degradation";

export interface AvatarPanelProps {
  vrmUrl: string;
  fallbackImage: string;
  width?: number;
  height?: number;
  onReady?: (handle: AvatarHandle) => void;
  onEvent?: (e: DegradationEvent) => void;
}

export function AvatarPanel(props: AvatarPanelProps) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let handle: AvatarHandle | null = null;
    let cancelled = false;
    if (host.current) {
      createAvatar(host.current, props).then((h) => {
        if (cancelled) h.dispose();
        else {
          handle = h;
          props.onReady?.(h);
        }
      });
    }
    return () => {
      cancelled = true;
      handle?.dispose();
    };
  }, [props.vrmUrl]);
  return <div ref={host} class="avatar-panel" role="img" aria-label="Avatar de la presentadora (voz sintética)" />;
}
