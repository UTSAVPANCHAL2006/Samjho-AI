// Line icons drawn in one style (24px grid, 1.8 stroke, round caps), so the app never mixes emoji with UI.

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 22, children, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      {...props}
    >
      {children}
    </svg>
  );
}

export const CameraIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.2l1.4-2h5.8l1.4 2h1.2A2.5 2.5 0 0 1 20 8.5v8A2.5 2.5 0 0 1 17.5 19h-11A2.5 2.5 0 0 1 4 16.5z" />
    <circle cx="12" cy="12.5" r="3.4" />
  </Icon>
);

export const BookIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v15H5.5A1.5 1.5 0 0 1 4 17.5z" />
    <path d="M20 5.5A1.5 1.5 0 0 0 18.5 4H13v15h5.5a1.5 1.5 0 0 0 1.5-1.5z" />
  </Icon>
);

export const NotebookIcon = (props: IconProps) => (
  <Icon {...props}>
    <rect x="5" y="3.5" width="14" height="17" rx="2" />
    <path d="M9 3.5v17M12 8h4M12 11.5h4M12 15h3" />
  </Icon>
);

export const PenIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="m14.5 5.5 4 4L9 19H5v-4z" />
    <path d="m12.5 7.5 4 4" />
  </Icon>
);

export const TargetIcon = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="4" />
    <circle cx="12" cy="12" r="0.6" fill="currentColor" />
  </Icon>
);

export const SigmaIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M17 5H7l5.5 7L7 19h10" />
  </Icon>
);

export const ChatIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6a2.5 2.5 0 0 1-2.5 2.5H11l-4 4v-4h0.5A2.5 2.5 0 0 1 5 12.5z" />
    <path d="M9 9.5h6" />
  </Icon>
);

export const SunIcon = (props: IconProps) => (
  <Icon {...props}>
    <circle cx="12" cy="12" r="3.5" />
    <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7M17 17l1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
  </Icon>
);

export const FrameIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16" />
  </Icon>
);

export const FlatIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M3 15.5 12 11l9 4.5-9 4.5z" />
  </Icon>
);

export const FlameIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M12 21c-3.6 0-6-2.4-6-5.6 0-3.4 2.6-5 3.6-8.4.9 1.6 1.4 2.8 1.4 4 1.4-.8 2.4-2.6 2.6-5 2.6 2.2 4.4 5.4 4.4 9.2 0 3.4-2.4 5.8-6 5.8z" />
  </Icon>
);

export const ArrowRightIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);

export const RetakeIcon = (props: IconProps) => (
  <Icon {...props}>
    <path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.7" />
    <path d="M20 4v4.7h-4.7" />
    <path d="M20 12a8 8 0 0 1-13.7 5.6L4 15.3" />
    <path d="M4 20v-4.7h4.7" />
  </Icon>
);
