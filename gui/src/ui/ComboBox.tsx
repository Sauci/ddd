import { useEffect, useRef } from "react";
import {
  Button as AriaButton,
  ComboBox as AriaComboBox,
  Collection,
  Header,
  Input,
  Label,
  ListBox,
  ListBoxItem,
  ListBoxSection,
  Popover,
  Text,
} from "react-aria-components";

export interface ComboChoice {
  id: string;
  label: string;
  detail: string;
}

export interface ComboSection {
  id: string;
  title: string;
  choices: readonly ComboChoice[];
}

interface Props {
  label: string;
  inputValue: string;
  onInputChange: (value: string) => void;
  sections: readonly ComboSection[];
  onPick: (id: string) => void;
  /** A line under the field, such as that a typed unit is not one of the project's. */
  note?: string | undefined;
  isDisabled?: boolean;
  /** Take the focus when shown, which opens the list: a unit cell hands the reader over. */
  autoFocus?: boolean;
}

/**
 * A field that offers choices in sections and takes any text typed: React Aria's ComboBox with
 * a custom value allowed. The caller narrows the sections itself (lib/units.ts knows what a
 * match is), so they are handed over as `items`, which React Aria does not filter again.
 */
export function ComboBox({
  label,
  inputValue,
  onInputChange,
  sections,
  onPick,
  note,
  isDisabled = false,
  autoFocus = false,
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);
  return (
    <AriaComboBox
      className="combo"
      items={sections}
      inputValue={inputValue}
      onInputChange={onInputChange}
      onSelectionChange={(key) => {
        if (key !== null) onPick(String(key));
      }}
      allowsCustomValue
      menuTrigger="focus"
      isDisabled={isDisabled}
    >
      <Label>{label}</Label>
      <div className="combo-field">
        <Input ref={input} />
        <AriaButton aria-label={`Show the choices for ${label}`}>▾</AriaButton>
      </div>
      {note !== undefined && (
        <Text slot="description" className="combo-note">
          {note}
        </Text>
      )}
      <Popover className="combo-popover">
        <ListBox<ComboSection> className="combo-list">
          {(section) => (
            <ListBoxSection id={section.id}>
              <Header>{section.title}</Header>
              <Collection items={section.choices}>
                {(choice) => (
                  <ListBoxItem id={choice.id} textValue={choice.label} className="combo-choice">
                    <Text slot="label">{choice.label}</Text>
                    <Text slot="description" className="combo-detail">
                      {choice.detail}
                    </Text>
                  </ListBoxItem>
                )}
              </Collection>
            </ListBoxSection>
          )}
        </ListBox>
      </Popover>
    </AriaComboBox>
  );
}
