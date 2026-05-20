import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Tailwind-aware class-name combiner. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
