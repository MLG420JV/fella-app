"""Fella's face — the squared, big-eyed design, rendered as SVG per mood.

Each function returns an SVG string. `body_hex` and `eye_hex` let the user's
chosen accent colour flow through, exactly like the settings mockup.
"""

MOODS = ("idle", "thinking", "happy", "asking", "sleeping")


def face_svg(mood: str = "idle", body_hex: str = "#A79FF0", eye_hex: str = "#26215C") -> str:
    body = f'<rect x="8" y="8" width="64" height="60" rx="16" fill="{body_hex}"/>'

    if mood == "happy":
        eyes = (
            f'<path d="M19 42 Q28 31 37 42" fill="none" stroke="{eye_hex}" stroke-width="5" stroke-linecap="round"/>'
            f'<path d="M43 42 Q52 31 61 42" fill="none" stroke="{eye_hex}" stroke-width="5" stroke-linecap="round"/>'
        )
    elif mood == "sleeping":
        eyes = (
            f'<path d="M19 38 Q28 45 37 38" fill="none" stroke="{eye_hex}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M43 38 Q52 45 61 38" fill="none" stroke="{eye_hex}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M56 14 h7 l-7 7 h7" fill="none" stroke="{eye_hex}" stroke-width="2.5" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="0.6"/>'
        )
    elif mood == "thinking":
        eyes = (
            f'<circle cx="30" cy="32" r="9.5" fill="{eye_hex}"/><circle cx="54" cy="32" r="9.5" fill="{eye_hex}"/>'
            f'<circle cx="33" cy="29" r="3" fill="#FFFFFF"/><circle cx="57" cy="29" r="3" fill="#FFFFFF"/>'
            f'<circle cx="24" cy="57" r="2" fill="{eye_hex}"/><circle cx="32" cy="57" r="2" fill="{eye_hex}"/>'
            f'<circle cx="40" cy="57" r="2" fill="{eye_hex}"/>'
        )
    elif mood == "asking":
        eyes = (
            f'<circle cx="28" cy="43" r="8" fill="{eye_hex}"/><circle cx="52" cy="43" r="8" fill="{eye_hex}"/>'
            f'<circle cx="30.5" cy="40.5" r="2.4" fill="#FFFFFF"/><circle cx="54.5" cy="40.5" r="2.4" fill="#FFFFFF"/>'
        )
    else:  # idle
        eyes = (
            f'<circle cx="28" cy="38" r="9.5" fill="{eye_hex}"/><circle cx="52" cy="38" r="9.5" fill="{eye_hex}"/>'
            f'<circle cx="31" cy="35" r="3" fill="#FFFFFF"/><circle cx="55" cy="35" r="3" fill="#FFFFFF"/>'
        )

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 76" width="80" height="76">'
        f'{body}{eyes}</svg>'
    )
