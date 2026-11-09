---
name: GestureGuard HMI
description: A local precision-engineering control center for intentional touchless interaction with simulated workstations.
colors:
  bg: "#0c1117"
  panel: "#141c24"
  panel-raised: "#19232c"
  line: "#2a3641"
  text: "#e6edf2"
  muted: "#98a8b5"
  faint: "#738592"
  teal: "#73d8bd"
  amber: "#edc07a"
  red: "#f19499"
  ink: "#0b2722"
  button-primary: "#85ddc5"
  button-primary-hover: "#a5edda"
  button-ink: "#102e29"
  button-secondary: "#19232d"
  button-secondary-hover: "#23313d"
  button-secondary-border: "#374450"
  button-secondary-text: "#c9d5df"
  nav-active: "#1e3435"
  nav-active-border: "#355251"
  nav-active-text: "#9ce3d1"
  badge-neutral: "#26313b"
  badge-neutral-text: "#b6c3cc"
  badge-neutral-border: "#3a4651"
  badge-teal: "#1c3532"
  badge-teal-text: "#94ddc8"
  badge-teal-border: "#31564d"
  badge-amber: "#342e25"
  badge-amber-text: "#e6c490"
  badge-amber-border: "#514738"
  badge-red: "#3b282d"
  badge-red-text: "#f2b0b3"
  badge-red-border: "#674047"
typography:
  page-heading:
    fontFamily: "Geist, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  section-heading:
    fontFamily: "Geist, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "-0.015em"
  panel-title:
    fontFamily: "Geist, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Geist, sans-serif"
    fontSize: "13px"
  operational-label:
    fontFamily: "Geist, sans-serif"
    fontSize: "11px"
  button:
    fontFamily: "Geist, sans-serif"
    fontSize: "11px"
    fontWeight: 550
  intent-heading:
    fontFamily: "Geist, sans-serif"
    fontSize: "20px"
    fontWeight: 550
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  station-value:
    fontFamily: "Geist, sans-serif"
    fontSize: "23px"
    fontWeight: 450
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  code:
    fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace"
    fontSize: "11px"
rounded:
  progress: "2px"
  key: "3px"
  badge: "4px"
  control: "5px"
  navigation: "6px"
  panel: "8px"
  intent-symbol: "11px"
spacing:
  micro: "4px"
  control-gap: "8px"
  compact-inset: "12px"
  panel-inset: "16px"
  desktop-gap: "17px"
  large-inset: "20px"
  wide-gap: "22px"
  guide-inset: "24px"
  presentation-gutter: "28px"
  desktop-gutter: "31px"
  wide-gutter: "42px"
components:
  button-primary:
    backgroundColor: "{colors.button-primary}"
    textColor: "{colors.button-ink}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 13px"
  button-primary-hover:
    backgroundColor: "{colors.button-primary-hover}"
  button-secondary:
    backgroundColor: "{colors.button-secondary}"
    textColor: "{colors.button-secondary-text}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "9px 13px"
  button-secondary-hover:
    backgroundColor: "{colors.button-secondary-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "#a6d8ca"
    typography: "{typography.operational-label}"
    padding: "5px 0"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
  badge-neutral:
    backgroundColor: "{colors.badge-neutral}"
    textColor: "{colors.badge-neutral-text}"
    typography: "{typography.operational-label}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  badge-amber:
    backgroundColor: "{colors.badge-amber}"
    textColor: "{colors.badge-amber-text}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
  field:
    backgroundColor: "#111d26"
    textColor: "#d4e5ed"
    typography: "{typography.operational-label}"
    rounded: "{rounded.badge}"
    padding: "9px"
  navigation-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.nav-active-text}"
    rounded: "{rounded.navigation}"
    padding: "12px"
  source-selected:
    backgroundColor: "#26353e"
    textColor: "#e2edf1"
    rounded: "{rounded.key}"
    padding: "5px 7px"
  intent-symbol:
    backgroundColor: "#25333c"
    textColor: "#bad1d7"
    rounded: "{rounded.intent-symbol}"
    height: "42px"
    width: "42px"
---

# Design System: GestureGuard HMI

## Overview

**Creative North Star: "Precision-engineering control center"**

Mode: **Operate**. The primary job is to see what the system detected, what it intends, and whether a command has committed. Use a composed, premium industrial interface: charcoal canvas, slightly raised slate surfaces, restrained teal, crisp cool borders and clear status language. Vision and intent receive the strongest hierarchy; navigation and supporting evidence recede.

This is a locally served FYP research prototype for three simulated industrial workstations. The user's operational brief takes precedence over generic landing-page guidance: retain useful operational density, direct controls and purposeful equipment diagrams. AIDA sequencing, random components, giant promotional spacing and decorative scroll motion do not define this product.

**Key Characteristics:**
- Dense but legible operational information, with small labels supporting clear values and action headings.
- Geometric equipment diagrams driven by deterministic simulation state.
- Source identity, pending intent, permissions and committed actions remain visibly distinguishable.
- Evidence stays honest: missing data stays missing, and simulation is always identified.

This document refreshes the original design direction from `PRODUCT.md` and `frontend/src/styles.css`. The supplied 1366px control-center and 1920px presentation screenshots show the final readability, projector-height and mobile-source corrections. The current CSS and its final audit overrides govern exact values. No camera hardware or live-camera accuracy verification is implied by this documentation.

## Colors

The palette uses cool charcoal and slate for structure, pale gray for reading, and limited semantic color for decisions and state. Frontmatter values preserve the CSS source values; similar one-off borders and text tints are contextual refinements rather than new semantic roles.

### Primary
- **Teal** (`teal`): affirmative system state, selected workstation check, progress, focus and restrained action cues.
- **Primary control teal** (`button-primary` / `button-primary-hover`): the filled confirmation and scenario-action surface, paired with dark `button-ink` text.

### Semantic States
- **Amber** (`amber`): waiting, pending intent and confirmation states; pair with explicit text and a warm dark surface.
- **Red** (`red`): rejection or error states; pair with a reason and the red badge/notice family. It is not a decorative accent.
- **Neutral badge**: stopped, locked and inactive states. A lock symbol or status dot supports the written label.

### Neutral
- **Charcoal canvas** (`bg`): the application background.
- **Slate panel** (`panel`) and **raised slate** (`panel-raised`): information grouping and controls.
- **Cool divider** (`line`): structural separation; most boundaries use a 1px stroke.
- **Primary text**, **muted text**, **faint text** (`text`, `muted`, `faint`): hierarchy for content, descriptions and peripheral information. Do not use faint text for the only expression of a critical decision.

**The State-with-Text Rule.** Color always accompanies words, a symbol, or a value. Amber does not by itself mean a request is executable, and teal does not prove an action committed.

## Typography

**Interface font:** locally bundled Geist, with `sans-serif` fallback. Use the same family for headings, controls and keyboard hints; use the monospace stack only for code-like content. Measurements, station numbering and timeline times use tabular numerals.

### Hierarchy
- **Page heading:** 28px / 600 / 1.2 with -0.035em tracking; 32px at widths of at least 1600px, 25px at 980px and below, and 23px at 760px and below.
- **Section heading:** normally 14px / 600 with -0.015em tracking. Panel headings are 12px by default and 14px on wide displays; the final mobile vision heading is 14px.
- **Intent heading:** 20px / 550 / 1.2 with -0.03em tracking; presentation emphasizes it at 29px, with 23px in mobile presentation.
- **Body:** the root is 13px, rising to 14px from 1600px. Paragraphs use line-height 1.65 unless their component specifies a tighter operational measure. Most compact descriptions are explicitly 11px; guide prose can be larger with a 65ch maximum.
- **Operational label:** 11px is the ordinary desktop operational floor. Small uppercase source/readout/navigation labels use restrained tracking, typically 0.08–0.13em. Keep text labels intact when controls reflow.
- **Station value:** 23px / 450 / 1.15 with -0.03em tracking and tabular numerals; units remain smaller and visually attached. Wide desktop values are 28px; presentation values are 27px.
- **Projector priority:** at widths above 760px, the final presentation overrides raise source/readout, state and station-detail labels to 12px and main action controls, operational status/mode text and intent explanation to 14px. Some peripheral text retains its existing 11px rule; do not describe projector mode as a global font-size substitution.

**The Readable-Evidence Rule.** Never shrink operational labels to solve overflow. Reflow controls, omit an established peripheral hint, or reduce nonessential diagram height first.

## Layout

The default shell is a 204px sidebar plus a flexible main column. Content is centered with a maximum width of 1800px and 27px top / 31px horizontal padding. The top bar is 61px tall. The operation strip precedes the main work area, then vision and intent, three workstations, scenario controls and the event timeline.

The desktop control grid uses `minmax(0, 1.8fr) minmax(285px, 1fr)` with a 17px gap. Workstations use three equal minimum-zero columns with the same gap. Panels normally use 14–18px horizontal insets; 4px and 8px support micro-spacing, while 12px, 16px, 17px, 20px and 22px set the practical rhythm. Preserve the explicit values already in CSS rather than replacing the system with a new generic spacing scale.

### Responsive constraints
- **At least 1600px:** 35px top / 42px horizontal content padding, 22px grid gaps and a `1.85fr` vision column with a 340px minimum intent column. The ordinary vision canvas is 326px tall.
- **1200px and below:** sidebar becomes 180px; content gutters become 22px; control/workstation gaps become 13px. Supporting hints and source icons may recede. An existing branding-only `.brand small` rule is 6px at this breakpoint; it is not an operational text token.
- **980px and below:** sidebar becomes a 64px icon rail and the top bar becomes 53px. Long navigation labels and sidebar footer content hide. Studio content stacks; evaluation columns remain two until the mobile breakpoint.
- **760px and below:** content gutters are 16px; vision and intent stack, workstations become a vertical list, forms wrap, and evaluation/guide layouts become one column. Workstation cards retain a two-column interior: diagram to the left, state/metrics to the right, action row across both columns. The body supports a minimum width of 360px.
- **Mobile source controls:** the vision heading becomes a vertical group with at least 90px height; all three source buttons occupy a full-width three-column grid, support wrapped text and use 8px / 4px button padding. The readout becomes two columns; stability hold spans both. Do not force source choices into a cramped header row.

### Presentation constraints
Presentation hides the sidebar, uses a 45px top bar, keeps the 1800px content maximum, and increases the importance of current intent and controls. Above 760px the final audit rules use 16px top / 28px horizontal content padding, a 260px vision canvas, 66px vision readout and 72px equipment diagrams. These final rules override earlier 330px/300px canvas and 91px diagram declarations. The main grid is `minmax(0, 1.9fr) minmax(340px, 1fr)`. Reduce peripheral material before sacrificing projector readability; the scenario subtitle and page footer hide in this mode. Mobile presentation still stacks, uses 17px / 18px page padding, a 300px canvas and 135px diagrams.

## Elevation & Depth

Depth is tonal and structural. The interface uses darker canvas, slightly lighter panels, inset control surfaces and 1px cool borders. The current system has no box-shadow vocabulary, gradients used as decorative lighting, glass treatment or floating-card elevation. The subtle 32px vision grid and geometric viewfinder are diagram context, not a claim that a camera is running.

Motion is brief and functional: navigation changes use 150ms background/color transitions; buttons use 160ms background/border/transform transitions and a 1px pressed translation. The fan rotor uses a 1.4s linear loop when represented as running; the loader uses a 0.8s loop. Progress/confirmation fills use no CSS transition so their position follows state directly. `prefers-reduced-motion: reduce` removes animations and transitions and restores automatic scrolling behavior; preserve the static state cues when motion disappears.

## Shapes

Use modest, engineered rounding: 8px panels, 6px navigation/strips, 5px buttons, 4px badges/fields, 3px keyboard/source controls and 2px progress tracks. The intent symbol is an 11px rounded square, while status dots, selection checks and slider thumbs are circles. Panel overflow clips internal dividers cleanly. Equipment is made from simple line-and-fill geometry with cool muted materials; do not introduce photorealistic industrial stock imagery or live-looking fake video.

## Components

### Buttons
Compact, explicit controls use a 5px radius, 9px / 13px padding, a 35px minimum height, 11px text and 550 weight. Primary buttons use the teal fill and dark ink; secondary buttons use slate fill, a 1px border and pale text. Secondary hover uses `button-secondary-hover` and a brighter border; text actions use an unfilled teal-tinted label. Small buttons have a 30px minimum height. Disabled controls use 0.38 opacity and a noninteractive cursor. Preserve semantic button elements and visible action names.

Every interactive button, link, input and select receives a 2px teal `:focus-visible` outline with 4px offset. The upload field uses `:focus-within` to expose its hidden file input's focus. Do not replace focus with hover-only feedback.

### Chips and state labels
Badges use 4px rounding, a 1px border, 4px / 7px padding, 11px type and a 6px status dot. Teal, amber and red each have a matched dark surface, border and readable text tint. Source labels remain distinct from command state: live, replay and simulated/injected input must remain explicitly identifiable. The model score label says that it is not a probability.

### Panels and workstation cards
Panels use a 1px boundary, 8px radius and a clipped slate background. Headers are divider-led and normally 48px tall; vision and intent headers are 45px by default. A selected workstation gains a green-gray border and filled teal circular check while retaining its text identity. State, units, controls and equipment visuals must agree with the deterministic model. Start with all workstations stopped.

### Inputs and fields
Use dark filled fields, a 1px cool border, modest 4px corners and 11px labels. Annotation controls use 9px padding, `#111d26` fill and `#3e5564` border. Scenario fields use the existing `#101920` variant. Keep units adjacent to values, associate labels with controls and allow forms to wrap before reducing text. Slider progress is muted, with a small pale-teal thumb; it does not imply a committed station change.

### Navigation and source selection
Navigation is a quiet workspace rail with a 6px active surface, teal-tinted active text, a thin border and a small active dot. Default navigation is 12px with 12px padding; hover uses a slightly brighter slate surface. Presentation removes the rail; narrower screens retain the established icon rail. Source tabs use a dark inset group, 3px individual corners and a selected slate fill/border. Retain source labels through the mobile reflow.

### Intent guard and evidence
The intent guard leads with a state symbol and clear heading, then proposed action, workstation and activation policy, followed by separate confirmation and cancellation. Amber means awaiting a decision, teal marks affirmative state, and red communicates rejection with a reason. An icon, written state and action availability support each tone. Preview does not equal execution: detection, pending intent, authorization, rejection and commitment must remain distinguishable. Start locked; reflect release gating and the active permission policy truthfully.

The operation strip, timeline, audit views and evaluation values form supporting evidence. Show units and sample counts for measured results; unavailable FPS, latency or metrics remain absent or use the established unavailable mark. Do not fill empty evidence with invented benchmarks, calibrated confidence claims or apparent camera results.

## Do's and Don'ts

### Do
- **Do** preserve the Operate hierarchy: detected input, intended action, permission/confirmation state, committed result and supporting evidence.
- **Do** label every simulated, replayed or injected source and keep the virtual-workstation/research-prototype context visible.
- **Do** keep source state, station state and intent state consistent with actual application data.
- **Do** retain keyboard/manual alternatives, teal focus rings, responsive reflow and reduced-motion behavior.
- **Do** use the final audit overrides for projector dimensions and mobile source layout.

### Don't
- **Don't** represent this interface as controlling physical industrial equipment or as a certified emergency stop.
- **Don't** imply camera operation, detection accuracy or hardware verification from a decorative hand, grid, diagram or screenshot.
- **Don't** fabricate measured results, sample counts, calibrated confidence probabilities or completed actions.
- **Don't** turn amber preview into a success treatment, or make color the sole state indicator.
- **Don't** introduce promotional landing-page sequencing, decorative scroll animation, stock pictures or an unrelated visual direction.


## Recognition Studio additions

The recognition usability revision preserves the industrial palette, Geist type and existing navigation. The dashboard prioritizes the expected next action and observed evidence, while raw score details move into Studio. Studio pairs the real preview with causal diagnostics and explicit source-specific score wording; geometry distance limits are not classifier thresholds. Unavailable live input presents camera recovery before gesture prompts. New operational labels and consent/methodology copy retain an11px floor with responsive wrapping. Recording has a distinct active state, unchecked voluntary consent, separate optional image consent, actual progress/counters and a measured-data empty state. Calibration application requires an independent explicit approval; no sample counts or benchmark results are invented.
