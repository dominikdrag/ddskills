# Feature canvas contract

Write one contract per canvas before any feature artboard. Every agent receives it verbatim; the cross-feature review checks artboards against it. Fill each section with the app's real terms; delete a section only when no feature touches it.

## Shared story

- **Today:** the fictional date every artboard shares (weekday, date, time for lock screens).
- **Cast:** 4–7 recurring people, records or items with the facts each feature may show (names, states, dates, notes, counts). Give each one role in the story so features can lean on the same examples.
- **Counts that appear on several screens:** state them once here ("Anna has 3 gift ideas; 2 linked to her birthday"). A number drawn on two artboards must agree.
- **Timeline:** when a feature creates data (a capture step adds an item), say which artboards show the state before and which after.

## Shared screens

For every screen more than one feature draws (a detail page, a settings page, a list, a form), write:

- the section order, top to bottom, naming which feature adds which section;
- the exact anatomy of shared components (card, row, header) with a pointer to the skeleton artboard;
- what each feature may add and where, and what no feature may change.

## Feature ownership

List, per feature, every UI element it adds (sections, lines on shared cards, chips, marks, notification lines, settings switches). Each lane draws the shipped app plus only its own elements. When a feature normally draws from another (a prep card listing another feature's items, a calendar showing another feature's marks), its lane shows only the shipped sources and the row's sticky names the extra ones. A package row may combine features and says so in its title.

## System surfaces

- Notifications: how many per day, the title and body pattern the app already ships, which lines features may add, and what never appears on a lock screen.
- Widgets, controls, Siri or share sheet: which exist today and which the features propose.

## Glossary

The app's domain terms with the words to avoid. Artboard copy uses these exactly, in the app's voice (sentence case, tone, punctuation).

## Tiers (paid features only)

- **Free:** everything shipped today, unchanged. Say what counts as a change (a new section, a badge, a rearranged list).
- **Paid:** the working name of the tier and how paid screens look to a paying user (usually: no badges).
- **Lapsed:** what stays (data readable, editable, deletable and exported; already scheduled reminders still fire), what stops (creating new paid items, paid views), and the single calm line that replaces a create action.
- **Discovery:** the main door (for example a settings card and a one-time what's-new sheet) and the limit per feature (for example one quiet entry point on a free screen, never inside the core flow or in notifications).
- **AI or device limits:** which features depend on on-device models, languages or hardware, and how ineligible users see them (usually: not at all).

## Content rules

The product's refusals that every artboard honours (for example: no scores or streaks, the app never writes messages for the user), plus accessibility minimums: real controls, 44 px targets, contrast.
