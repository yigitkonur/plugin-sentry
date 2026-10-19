import type { ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary";
}

export function Button({ variant = "primary", className, ...rest }: ButtonProps) {
  return <button className={`ui-button ui-button--${variant} ${className ?? ""}`} {...rest} />;
}
