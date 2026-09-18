import { Button as AriaButton, type ButtonProps } from "react-aria-components";

type Variant = "primary" | "secondary" | "link";

interface Props extends Omit<ButtonProps, "className"> {
  variant?: Variant;
}

/** A button in one of the page's three looks: the one action of a view, any other, or a link. */
export function Button({ variant = "secondary", ...props }: Props) {
  return <AriaButton {...props} className={`button ${variant}`} />;
}
