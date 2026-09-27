import { Button } from "./ui";

interface OptionButtonsProps {
  options: string[];
  current: string | null;
  pending: string | null;
  disabled?: boolean;
  onPick: (option: string) => void;
}

/** Row of pill buttons for moods. */
export function OptionButtons({
  options,
  current,
  pending,
  disabled,
  onPick,
}: OptionButtonsProps) {
  if (options.length === 0) {
    return (
      <div className="muted">No options yet — map them under Manage.</div>
    );
  }
  return (
    <div className="row">
      {options.map((option) => {
        const isCurrent = option === current;
        const isPending = option === pending;
        return (
          <Button
            key={option}
            variant={isCurrent ? "default" : "outline"}
            className={isPending && !isCurrent ? "pending" : ""}
            disabled={disabled}
            onClick={() => onPick(option)}
          >
            {option}
            {isPending && !isCurrent ? " …" : ""}
          </Button>
        );
      })}
    </div>
  );
}
