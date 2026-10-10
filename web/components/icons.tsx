import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Icon({ children, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export function MenuIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 7h16M4 12h16M4 17h16" /></Icon>;
}

export function PlusIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 5v14M5 12h14" /></Icon>;
}

export function SendIcon(props: IconProps) {
  return <Icon {...props}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></Icon>;
}

export function SparkIcon(props: IconProps) {
  return <Icon {...props}><path d="M12 3c.55 4.5 3 6.95 7.5 7.5-4.5.55-6.95 3-7.5 7.5-.55-4.5-3-6.95-7.5-7.5C9 9.95 11.45 7.5 12 3Z" /></Icon>;
}

export function BookIcon(props: IconProps) {
  return <Icon {...props}><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" /></Icon>;
}

export function CloseIcon(props: IconProps) {
  return <Icon {...props}><path d="m6 6 12 12M18 6 6 18" /></Icon>;
}

export function LeafIcon(props: IconProps) {
  return <Icon {...props}><path d="M5 21c6-1 11-5 14-13" /><path d="M6 17C2 12 5 5 20 3c1 12-5 17-14 14Z" /></Icon>;
}

export function SpeakerIcon(props: IconProps) {
  return <Icon {...props}><path d="M11 5 6 9H3v6h3l5 4V5Z" /><path d="M15.5 8.5a5 5 0 0 1 0 7" /><path d="M18 6a8.5 8.5 0 0 1 0 12" /></Icon>;
}

export function PauseIcon(props: IconProps) {
  return <Icon {...props}><path d="M9 5v14M15 5v14" /></Icon>;
}

export function PlayIcon(props: IconProps) {
  return <Icon {...props}><path d="m8 5 11 7-11 7V5Z" /></Icon>;
}
