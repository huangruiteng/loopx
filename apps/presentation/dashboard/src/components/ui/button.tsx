import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex h-9 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md border px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50 dark:focus-visible:ring-zinc-500",
  {
    variants: {
      variant: {
        primary: "border-slate-900 bg-slate-950 text-white hover:bg-slate-800 dark:border-zinc-100 dark:bg-zinc-50 dark:text-zinc-950 dark:hover:bg-zinc-200",
        secondary: "border-slate-200 bg-white text-slate-900 hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:bg-zinc-900",
        ghost: "border-transparent bg-transparent text-slate-700 hover:bg-slate-100 dark:text-zinc-300 dark:hover:bg-zinc-900",
      },
      size: {
        sm: "h-8 px-2 text-xs",
        md: "h-9 px-3 text-sm",
        icon: "h-9 w-9 px-0",
      },
    },
    defaultVariants: {
      variant: "secondary",
      size: "md",
    },
  },
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: ButtonProps) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      type="button"
      {...props}
    />
  );
}
