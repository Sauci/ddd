import { useEffect, useRef, useState } from "react";
import {
  Button as AriaButton,
  ComboBox as AriaComboBox,
  Collection,
  Group,
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
  /**
   * An entry of the list taken: pressed, or focused - with the arrow keys, or by the pointer
   * resting on it - and taken with Enter, or with Tab as the reader moves on, which is how React
   * Aria's ComboBox takes a focused entry. Text typed is never taken this way.
   */
  onPick: (id: string) => void;
  /**
   * Enter pressed with no entry of the list focused, with the text the field holds: the caller
   * says which choice that text names, since only it knows what a match is.
   */
  onEnter: (text: string) => void;
  /**
   * The list closed, whether an entry was taken or not - by Enter, Escape, Tab, ▾ or the focus
   * leaving the field. The caller puts its own value back in the field: text typed and left is
   * never a choice.
   */
  onClose: () => void;
  /** A line under the field, such as that a typed unit is not one of the project's. */
  note?: string | undefined;
  isDisabled?: boolean;
  /**
   * Take the focus when this changes to a new value: a unit cell hands the reader over, even on
   * a second press of the same cell - a plain boolean would not change between two such
   * presses, and the field would not take the focus back. `null` asks for no focus.
   */
  autoFocus?: number | null;
  /**
   * What opens the list: typing, ArrowDown or ▾ ("input"), or also the field taking the focus
   * ("focus") - which only a story wants, to photograph the list open. Opened on focus, the list
   * covers what is below the field and hides the rest of the page from assistive technology.
   */
  menuTrigger?: "input" | "focus" | undefined;
}

/**
 * A field that offers choices in sections and takes any text typed: React Aria's ComboBox with
 * a custom value allowed. The caller narrows the sections itself (lib/units.ts knows what a
 * match is), so they are handed over as `items`, which React Aria does not filter again.
 *
 * An entry is taken as an action rather than selected: React Aria keeps no selection of its own
 * here, so nothing it remembers can disagree with the caller's choice or be taken by Enter in
 * its place.
 */
export function ComboBox({
  label,
  inputValue,
  onInputChange,
  sections,
  onPick,
  onEnter,
  onClose,
  note,
  isDisabled = false,
  autoFocus = null,
  menuTrigger = "input",
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  // React Aria opens the list whenever the field's text changes while it has the focus, whoever
  // changed it. When the list closes, the caller puts its own value back in the field, which is
  // no reason to open it again: until the reader types or leaves the field, only ArrowDown or ▾
  // opens it.
  const [puttingBack, setPuttingBack] = useState(false);
  useEffect(() => {
    if (autoFocus !== null) input.current?.focus();
  }, [autoFocus]);
  return (
    <AriaComboBox
      className="combo"
      items={sections}
      inputValue={inputValue}
      onInputChange={(value) => {
        setPuttingBack(false);
        onInputChange(value);
      }}
      onOpenChange={(isOpen) => {
        if (isOpen) return;
        setPuttingBack(true);
        onClose();
      }}
      allowsCustomValue
      menuTrigger={puttingBack ? "manual" : menuTrigger}
      isDisabled={isDisabled}
    >
      <Label>{label}</Label>
      {/* A Group, so that the list is placed against the whole field and as wide as it: without
          one, React Aria measures the input and its button alone. */}
      <Group className="combo-field">
        <Input
          ref={input}
          onKeyDown={(event) => {
            // React Aria has handled the key already, closing the list, and with an entry focused
            // it took that entry. Whether one was is read from the field's aria-activedescendant,
            // which still describes the list as the key found it: the page is not drawn again
            // before the key's handlers have all run.
            if (
              event.key === "Enter" &&
              !event.currentTarget.hasAttribute("aria-activedescendant")
            ) {
              onEnter(inputValue);
            }
          }}
          // Leaving the field ends the putting back - React Aria has closed the list before this
          // runs - so that the field taking the focus again opens the list as `menuTrigger` says.
          onBlur={() => setPuttingBack(false)}
        />
        <AriaButton aria-label={`Show the choices for ${label}`}>▾</AriaButton>
      </Group>
      {note !== undefined && (
        <Text slot="description" className="combo-note">
          {note}
        </Text>
      )}
      {/* No offset of React Aria's own: the gap under the field is ui.css's margin alone, the
          chosen mockup's. Measured from the Group, React Aria's 8px would add to it. */}
      <Popover className="combo-popover" offset={0}>
        <ListBox<ComboSection> className="combo-list">
          {(section) => (
            <ListBoxSection id={section.id}>
              <Header>{section.title}</Header>
              <Collection items={section.choices}>
                {(choice) => (
                  <ListBoxItem
                    id={choice.id}
                    textValue={choice.label}
                    className="combo-choice"
                    onAction={() => onPick(choice.id)}
                  >
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
