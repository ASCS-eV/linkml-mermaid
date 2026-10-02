"""Mermaid ``stateDiagram-v2`` renderer.

Consumes :class:`~linkml_mermaid.types.MermaidState` and
:class:`~linkml_mermaid.types.MermaidTransition` objects and produces a
syntactically valid ``stateDiagram-v2`` code block.

**This renderer is pure** — it knows nothing about LinkML, YAML files,
or any particular domain model.  Mapping from LinkML data to these
Mermaid types is handled by :mod:`linkml_mermaid.mapping`.

Specification references
========================

Mermaid stateDiagram-v2 — full spec
    https://mermaid.js.org/syntax/stateDiagram.html

§States
    https://mermaid.js.org/syntax/stateDiagram.html#states
    Three declaration forms:
    1. Bare id:  ``s1``
    2. Keyword:  ``state "description" as s1``
    3. Colon:    ``s1 : description``
    This renderer uses form (3) when ``label != id``.

§Transitions
    https://mermaid.js.org/syntax/stateDiagram.html#transitions
    "Transitions are path/edges when one state passes into another.
     This is represented using text arrow, '-->'.  It is possible to
     add text to a transition to describe what it represents."

§Start and End
    https://mermaid.js.org/syntax/stateDiagram.html#start-and-end
    "There are two special states indicating the start and stop of the
     diagram. These are written with the [*] syntax and the direction
     of the transition to it defines it either as a start or a stop
     state."

§Notes
    https://mermaid.js.org/syntax/stateDiagram.html#notes
    "Here you can choose to put the note to the right of or to the
     left of a node."
    Syntax: ``note right of StateId : text``

§Setting the direction of the diagram
    https://mermaid.js.org/syntax/stateDiagram.html#setting-the-direction-of-the-diagram
    "With state diagrams you can use the direction statement to set
     the direction which the diagram will render."
    Values: TB (top-bottom), LR (left-right), BT, RL.

§Composite states
    https://mermaid.js.org/syntax/stateDiagram.html#composite-states
    "In order to define a composite state you need to use the state
     keyword followed by an id and the body of the composite state
     between {}."
    Not yet implemented in this renderer — noted for future extension.

§Choice
    https://mermaid.js.org/syntax/stateDiagram.html#choice
    "Sometimes you need to model a choice between two or more paths,
     you can do so using <<choice>>."
    Not yet implemented — noted for future extension.

§Forks
    https://mermaid.js.org/syntax/stateDiagram.html#forks
    "It is possible to specify a fork in the diagram using
     <<fork>> <<join>>."
    Not yet implemented — noted for future extension.

§Spaces in state names
    https://mermaid.js.org/syntax/stateDiagram.html#spaces-in-state-names
    "Spaces can be added to a state by first defining the state with
     an id and then referencing the id later."
    Our ``to_state_id()`` avoids spaces by converting to PascalCase.

§Styling with classDefs
    https://mermaid.js.org/syntax/stateDiagram.html#styling-with-classdefs
    Not yet implemented — noted for future extension.
"""

from __future__ import annotations

import re

from .escaping import escape_state_inline, escape_state_label
from .types import MermaidNote, MermaidState, MermaidTransition

# Directions documented in §Setting the direction of the diagram.
# "TD" is deliberately absent: the flowchart docs define it, the
# stateDiagram docs do not.
STATE_DIAGRAM_DIRECTIONS = frozenset({"TB", "BT", "RL", "LR"})

_NON_ALPHANUMERIC_RE = re.compile(r"[^0-9A-Za-z]+")


def to_state_id(label: str) -> str:
    """Convert a human-readable label to a valid Mermaid state ID.

    Applies PascalCase and strips every non-alphanumeric character:
    ``"Content review"`` → ``"ContentReview"``,
    ``"Draft (new)"`` → ``"DraftNew"``,
    ``"IN_REVIEW"`` → ``"InReview"``.

    Capitalisation already present inside a word is preserved, so
    ``"ContentReview"`` round-trips unchanged rather than collapsing to
    ``"Contentreview"``.  A multi-word label that is entirely uppercase
    is recognised as SCREAMING_SNAKE_CASE and title-cased instead.

    The conversion is idempotent: feeding a result back in returns it
    unchanged, so regenerating a diagram from ids this function already
    produced is stable.

    Mermaid ids may not begin with a digit, so a leading-digit result is
    prefixed with ``S``: ``"2nd pass"`` → ``"S2ndPass"``.

    Per §Spaces in state names, Mermaid requires an id without spaces to
    be defined first, then referenced by that id in transitions.
    PascalCase gives clean, readable identifiers.

    Raises:
        ValueError: If *label* contains no alphanumeric characters and
            therefore yields no usable identifier.  Returning ``""``
            would emit a syntactically invalid diagram.
    """
    words = [w for w in _NON_ALPHANUMERIC_RE.split(label) if w]

    # Only a separated, fully uppercase label is treated as screaming
    # snake case. Applying the rule word-by-word would also rewrite an
    # unseparated result such as "A1B2", breaking idempotency.
    screaming = len(words) > 1 and label.isupper()
    state_id = "".join(w.capitalize() if screaming else w[0].upper() + w[1:] for w in words)

    if not state_id:
        raise ValueError(
            f"Cannot derive a Mermaid state id from {label!r}: "
            "it contains no alphanumeric characters"
        )
    if state_id[0].isdigit():
        state_id = f"S{state_id}"
    return state_id


class StateDiagramRenderer:
    """Render a Mermaid ``stateDiagram-v2`` from abstract state/transition
    objects.

    Produces output that conforms to the Mermaid stateDiagram-v2 spec:
    https://mermaid.js.org/syntax/stateDiagram.html

    The output does **not** include fenced code block markers
    (````mermaid`` / ``````) — the caller decides how to embed the
    diagram (inline markdown, HTML, etc.).

    Parameters:
        direction: Diagram layout direction per §Setting the direction.
            ``"TB"`` (top-bottom), ``"LR"`` (left-right), ``"BT"``,
            ``"RL"``, or *None* to omit (Mermaid default is TB).

    Example::

        states = [
            MermaidState(id="Draft", label="Draft", is_initial=True),
            MermaidState(id="Approved", is_terminal=True),
        ]
        transitions = [
            MermaidTransition("Draft", "Approved", label="Approve [RM]"),
        ]
        renderer = StateDiagramRenderer()
        print(renderer.render(states, transitions))
    """

    def __init__(self, direction: str | None = None) -> None:
        if direction is not None and direction not in STATE_DIAGRAM_DIRECTIONS:
            raise ValueError(
                f"Invalid direction '{direction}'; must be one of "
                f"{sorted(STATE_DIAGRAM_DIRECTIONS)} or None"
            )
        self._direction = direction

    def render(
        self,
        states: list[MermaidState],
        transitions: list[MermaidTransition],
        notes: list[MermaidNote] | None = None,
    ) -> str:
        """Produce the complete ``stateDiagram-v2`` text.

        Output structure follows the conventional ordering:
        1. Diagram type declaration
        2. Direction directive (§Setting the direction)
        3. Start pseudo-state transitions (§Start and End)
        4. State labels (§States, colon form)
        5. Transitions (§Transitions)
        6. End pseudo-state transitions (§Start and End)
        7. Notes (§Notes)
        """
        lines: list[str] = ["stateDiagram-v2"]

        # §Setting the direction of the diagram
        if self._direction:
            lines.append(f"    direction {self._direction}")

        # §Start and End — [*] --> InitialState
        for s in states:
            if s.is_initial:
                lines.append(f"    [*] --> {s.id}")

        lines.append("")

        # §States — every state is declared explicitly.
        #
        # Three forms are documented; which one applies depends on the
        # label:
        #   * ``StateId : label`` (colon form) when there is a distinct
        #     label to show.
        #   * ``state "label" as StateId`` when that label contains a
        #     colon, because the colon form runs to the end of the line
        #     and would otherwise be ambiguous (§Spaces in state names).
        #   * bare ``StateId`` otherwise.
        #
        # The bare form matters: a state that carries no distinct label
        # and takes part in no transition would never be mentioned
        # anywhere else, so omitting it would silently drop it from the
        # diagram. Attaching a note to such a state produces output that
        # parses but fails to render.
        for s in states:
            if s.label and s.label != s.id:
                label = escape_state_label(s.label)
                if ":" in label:
                    lines.append(f'    state "{label}" as {s.id}')
                else:
                    lines.append(f"    {s.id} : {label}")
            else:
                lines.append(f"    {s.id}")

        # §Transitions — FromState --> ToState : label
        #
        # The label is introduced by ":" and has no quoted form, so any
        # colon it contains must be escaped — "::" would otherwise be
        # read as the class-application operator.
        for t in transitions:
            if t.label:
                label = escape_state_inline(t.label)
                lines.append(f"    {t.from_state} --> {t.to_state} : {label}")
            else:
                lines.append(f"    {t.from_state} --> {t.to_state}")

        # §Start and End — TerminalState --> [*]
        lines.append("")
        for s in states:
            if s.is_terminal:
                lines.append(f"    {s.id} --> [*]")

        # §Notes — note {position} of {state_id} : {text}
        #
        # Like a transition label, the note body is introduced by ":"
        # and cannot be quoted, so colons in the text are escaped.
        if notes:
            lines.append("")
            for n in notes:
                lines.append(
                    f"    note {n.position} of {n.state_id} : {escape_state_inline(n.text)}"
                )

        return "\n".join(lines)
