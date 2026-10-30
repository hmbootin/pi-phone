interface Props {
  src: string;
  autoPlay?: boolean;
  onPlay?: () => void;
  label?: string;
}

export function AudioPlayer({ src, autoPlay, onPlay, label }: Props) {
  return (
    <audio controls preload="none" src={src} autoPlay={autoPlay} onPlay={onPlay} aria-label={label ?? 'Audio'}>
      Your browser can&apos;t play this audio. <a href={src}>Download it</a> instead.
    </audio>
  );
}
