from pathlib import Path
import re
import shutil
import html

# ============================================================
# CONFIGURATION
# ============================================================

LATEX_FILE = Path("overleaf_source/00_foundations/10_mathematical_writing_problem_solving.tex")
PTX_FILE = Path("source/01_foundations/10_mathematical_writing_problem_solving.ptx")

PLACEHOLDER_TEXT = "Content for this section will be added here."


# ============================================================
# BASIC HELPERS
# ============================================================

def slugify(text):
    text = re.sub(r"\\[A-Za-z]+", "", text)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text)
    text = text.strip("-").lower()
    return text or "untitled"


def label_to_id(label):
    label = label.strip()
    label = re.sub(r"[^A-Za-z0-9_.:-]+", "-", label)
    return label.replace(":", "-")


def escape_math(text):
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def escape_text(text):
    return html.escape(text, quote=False)


def strip_comments(text):
    lines = []

    for line in text.splitlines():
        result = []
        escaped = False

        for char in line:
            if char == "%" and not escaped:
                break

            result.append(char)

            if char == "\\":
                escaped = not escaped
            else:
                escaped = False

        lines.append("".join(result))

    return "\n".join(lines)


# ============================================================
# BALANCED BRACE READER
# ============================================================

def read_braced(text, start):
    if start >= len(text) or text[start] != "{":
        return None, start

    depth = 0

    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1

        elif text[i] == "}":
            depth -= 1

            if depth == 0:
                return text[start + 1:i], i + 1

    return None, start


# ============================================================
# LABEL EXTRACTION
# ============================================================

def extract_leading_label(text):
    match = re.match(
        r"\s*\\label\{([^}]+)\}",
        text,
        flags=re.S
    )

    if not match:
        return None, text

    label = match.group(1).strip()
    remaining = text[match.end():]

    return label, remaining


# ============================================================
# PROTECTED INLINE CONVERSION
# ============================================================

def convert_inline(text):
    protected = []

    def protect(value):
        token = f"@@PROTECTED{len(protected)}@@"
        protected.append(value)
        return token

    # --------------------------------------------------------
    # Inline math
    # --------------------------------------------------------

    def math_repl(match):
        math = escape_math(match.group(1).strip())
        return protect(f"<m>{math}</m>")

    text = re.sub(
        r"\\\((.*?)\\\)",
        math_repl,
        text,
        flags=re.S
    )

    # --------------------------------------------------------
    # References
    # --------------------------------------------------------

    def xref_repl(match):
        target = label_to_id(match.group(1))
        return protect(f'<xref ref="{target}" />')

    text = re.sub(
        r"\\(?:cref|Cref|ref)\{([^}]+)\}",
        xref_repl,
        text
    )

    # --------------------------------------------------------
    # Emphasis
    # --------------------------------------------------------

    def command_with_braces(command, tag):
        nonlocal text

        pattern = re.compile(rf"\\{command}\{{")

        while True:
            match = pattern.search(text)

            if not match:
                break

            start = match.end() - 1
            content, end = read_braced(text, start)

            if content is None:
                break

            converted = convert_inline(content)
            replacement = protect(
                f"<{tag}>{converted}</{tag}>"
            )

            text = text[:match.start()] + replacement + text[end:]

    command_with_braces("emph", "em")
    command_with_braces("textbf", "em")
    command_with_braces("textit", "em")

    # --------------------------------------------------------
    # TeX quotes
    # --------------------------------------------------------

    text = re.sub(
        r"``(.*?)''",
        lambda m: protect(
            f"<q>{convert_inline(m.group(1))}</q>"
        ),
        text,
        flags=re.S
    )

    # --------------------------------------------------------
    # Common escaped characters
    # --------------------------------------------------------

    text = text.replace(r"\%", "%")
    text = text.replace(r"\&", "&")
    text = text.replace(r"\_", "_")
    text = text.replace("~", " ")

    # Escape remaining ordinary XML text
    text = escape_text(text)

    # Restore protected XML
    for i, value in enumerate(protected):
        text = text.replace(
            f"@@PROTECTED{i}@@",
            value
        )

    return text


# ============================================================
# DISPLAY MATH PROTECTION
# ============================================================

def protect_display_math(text):
    protected = []

    def repl(match):
        token = f"@@DISPLAY{len(protected)}@@"

        math = match.group(1).strip()
        math = escape_math(math)

        protected.append(
            f"<p>\n<md>{math}</md>\n</p>"
        )

        # Blank lines force the placeholder to become
        # its own block rather than being wrapped in <p>.
        return f"\n\n{token}\n\n"

    text = re.sub(
        r"\\\[(.*?)\\\]",
        repl,
        text,
        flags=re.S
    )

    return text, protected

# ============================================================
# LIST CONVERSION
# ============================================================

def convert_list_environment(text, env, tag):
    pattern = re.compile(
        rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}",
        flags=re.S
    )

    def repl(match):
        body = match.group(1)

        items = re.split(
            r"\\item(?:\[[^\]]*\])?",
            body
        )

        items = [
            item.strip()
            for item in items
            if item.strip()
        ]

        xml_items = []

        for item in items:
            item_xml = convert_block(item)
            xml_items.append(
                f"<li>\n{item_xml}\n</li>"
            )

        return (
            f"<p>\n"
            f"<{tag}>\n"
            + "\n".join(xml_items)
            + f"\n</{tag}>\n"
            f"</p>"
        )

    while pattern.search(text):
        text = pattern.sub(repl, text)

    return text


# ============================================================
# CUSTOM ENVIRONMENTS
# ============================================================

def convert_definition_boxes(text):
    pattern = re.compile(
        r"\\begin\{definitionbox\}"
        r"(?:\{([^{}]*)\})?"
        r"(.*?)"
        r"\\end\{definitionbox\}",
        flags=re.S
    )

    def repl(match):
        title = (match.group(1) or "Definition").strip()
        body = match.group(2).strip()

        return (
            "<definition>\n"
            f"<title>{convert_inline(title)}</title>\n"
            "<statement>\n"
            f"{convert_block(body)}\n"
            "</statement>\n"
            "</definition>"
        )

    while pattern.search(text):
        text = pattern.sub(repl, text)

    return text


def convert_answer_boxes(text):
    pattern = re.compile(
        r"\\begin\{answerbox\}"
        r"(.*?)"
        r"\\end\{answerbox\}",
        flags=re.S
    )

    def repl(match):
        body = match.group(1).strip()

        return (
            "<solution>\n"
            f"{convert_block(body)}\n"
            "</solution>"
        )

    while pattern.search(text):
        text = pattern.sub(repl, text)

    return text


def convert_worked_examples(text):
    pattern = re.compile(
        r"\\begin\{workedexamplebox\}"
        r"(?:\{([^{}]*)\})?"
        r"(.*?)"
        r"\\end\{workedexamplebox\}",
        flags=re.S
    )

    def repl(match):
        title = (
            match.group(1)
            or "Worked Example"
        ).strip()

        body = match.group(2).strip()

        answer_match = re.search(
            r"\\begin\{answerbox\}"
            r"(.*?)"
            r"\\end\{answerbox\}",
            body,
            flags=re.S
        )

        answer_xml = ""

        if answer_match:
            answer_body = (
                answer_match.group(1).strip()
            )

            body = (
                body[:answer_match.start()]
                + body[answer_match.end():]
            )

            converted_answer = convert_block(
                answer_body
            )

            answer_xml = (
                "\n<p><em>Solution.</em></p>\n"
                + converted_answer
            )

        body_xml = convert_block(body)

        return (
            "<example>\n"
            f"<title>{convert_inline(title)}</title>\n"
            f"{body_xml}"
            f"{answer_xml}\n"
            "</example>"
        )

    while pattern.search(text):
        text = pattern.sub(repl, text)

    return text

def convert_exercises(text):
    pattern = re.compile(
        r"\\begin\{exercise\}"
        r"(?:\[[^\]]*\])?"
        r"(.*?)"
        r"\\end\{exercise\}",
        flags=re.S
    )

    def repl(match):
        body = match.group(1).strip()

        return (
            "<exercise>\n"
            "<statement>\n"
            f"{convert_block(body)}\n"
            "</statement>\n"
            "</exercise>"
        )

    while pattern.search(text):
        text = pattern.sub(repl, text)

    return text


# ============================================================
# TABLES AND COMPLEX LATEX
# ============================================================

def convert_tables(text):
    pattern = re.compile(
        r"\\begin\{tabularx\}"
        r".*?"
        r"\\end\{tabularx\}",
        flags=re.S
    )

    def repl(match):
        return (
            "<p><em>Manual conversion required:</em> "
            "This table from the LaTeX source still needs "
            "to be converted to native PreTeXt.</p>"
        )

    return pattern.sub(repl, text)


def remove_center_environment(text):
    text = text.replace(
        r"\begin{center}",
        ""
    )

    text = text.replace(
        r"\end{center}",
        ""
    )

    return text


# ============================================================
# PROJECT-SPECIFIC COMMANDS
# ============================================================

def convert_named_command(text, command, title):
    marker = "\\" + command + "{"

    while marker in text:
        start = text.find(marker)
        brace_start = start + len(marker) - 1

        content, end = read_braced(
            text,
            brace_start
        )

        if content is None:
            break

        body = convert_block(content)

        replacement = (
            "<remark>\n"
            f"<title>{title}</title>\n"
            f"{body}\n"
            "</remark>"
        )

        text = (
            text[:start]
            + replacement
            + text[end:]
        )

    return text


def convert_project_commands(text):
    text = convert_named_command(
        text,
        "prerequisite",
        "Prerequisites"
    )

    text = convert_named_command(
        text,
        "learningobjectives",
        "Learning Objectives"
    )

    text = convert_named_command(
        text,
        "chapterconnection",
        "Chapter Connection"
    )

    return text


# ============================================================
# PARAGRAPH CONVERSION
# ============================================================

BLOCK_XML_START = (
    "<p",
    "<definition",
    "<example",
    "<exercise",
    "<remark",
    "<note",
    "<warning",
    "<solution",
    "<proof",
    "<figure",
    "<table",
    "<sidebyside",
)



def protect_generated_xml_blocks(text):
    protected = []

    patterns = [
        r"<definition(?:\s[^>]*)?>.*?</definition>",
        r"<example(?:\s[^>]*)?>.*?</example>",
        r"<exercise(?:\s[^>]*)?>.*?</exercise>",
        r"<remark(?:\s[^>]*)?>.*?</remark>",
        r"<note(?:\s[^>]*)?>.*?</note>",
        r"<warning(?:\s[^>]*)?>.*?</warning>",
        r"<proof(?:\s[^>]*)?>.*?</proof>",
        r"<p>\s*<(?:ul|ol)>.*?</(?:ul|ol)>\s*</p>",
    ]

    combined = re.compile(
        "(" + "|".join(patterns) + ")",
        flags=re.S
    )

    def repl(match):
        token = (
            f"@@XMLBLOCK{len(protected)}@@"
        )

        protected.append(
            match.group(0)
        )

        return f"\n\n{token}\n\n"

    text = combined.sub(repl, text)

    return text, protected


def paragraphs_from_text(text):
    pieces = re.split(
        r"\n\s*\n",
        text.strip()
    )

    output = []

    for piece in pieces:
        piece = piece.strip()

        if not piece:
            continue

        if re.fullmatch(
            r"@@DISPLAY\d+@@",
            piece
        ):
            output.append(piece)
            continue

        if re.fullmatch(
            r"@@XMLBLOCK\d+@@",
            piece
        ):
            output.append(piece)
            continue

        if piece.startswith(
            BLOCK_XML_START
        ):
            output.append(piece)
            continue

        converted = convert_inline(
            piece
        ).strip()

        if converted:
            output.append(
                f"<p>{converted}</p>"
            )

    return "\n\n".join(output)

# ============================================================
# GENERAL BODY CONVERSION
# ============================================================

def convert_block(text):
    text = text.strip()

    if not text:
        return ""

    # Protect display mathematics first.
    text, displays = protect_display_math(
        text
    )

    text = remove_center_environment(
        text
    )

    text = convert_tables(text)

    text = convert_worked_examples(
        text
    )

    text = convert_definition_boxes(
        text
    )

    text = convert_exercises(
        text
    )

    text = convert_list_environment(
        text,
        "itemize",
        "ul"
    )

    text = convert_list_environment(
        text,
        "enumerate",
        "ol"
    )

    text = convert_project_commands(
        text
    )

    text = re.sub(
        r"\\nocite\{[^}]*\}",
        "",
        text
    )

    # Protect any PreTeXt XML that the converters
    # above have already generated.  This prevents
    # paragraphs_from_text() from escaping closing
    # tags or wrapping them in another <p>.
    text, xml_blocks = (
        protect_generated_xml_blocks(text)
    )

    result = paragraphs_from_text(
        text
    )

    # Restore generated PreTeXt blocks.
    for i, value in enumerate(xml_blocks):
        result = result.replace(
            f"@@XMLBLOCK{i}@@",
            value
        )

    # Restore display mathematics last.
    for i, value in enumerate(displays):
        result = result.replace(
            f"@@DISPLAY{i}@@",
            value
        )

    return result.strip()

# ============================================================
# STRUCTURAL PARSER
# ============================================================

def find_structural_commands(text):
    pattern = re.compile(
        r"\\(section|subsection|subsubsection)\{"
    )

    results = []

    for match in pattern.finditer(text):
        command = match.group(1)

        brace_start = match.end() - 1
        title, end = read_braced(
            text,
            brace_start
        )

        if title is None:
            continue

        results.append({
            "type": command,
            "title": title.strip(),
            "start": match.start(),
            "content_start": end,
        })

    return results


def parse_subsubsections(text):
    commands = [
        c for c in find_structural_commands(text)
        if c["type"] == "subsubsection"
    ]

    if not commands:
        return convert_block(text)

    output = []

    intro = text[:commands[0]["start"]]

    if intro.strip():
        output.append(
            convert_block(intro)
        )

    for index, command in enumerate(commands):
        next_start = (
            commands[index + 1]["start"]
            if index + 1 < len(commands)
            else len(text)
        )

        body = text[
            command["content_start"]:
            next_start
        ]

        label, body = extract_leading_label(body)

        xml_id = (
            label_to_id(label)
            if label
            else "subsubsec-" + slugify(command["title"])
        )

        output.append(
            f'<subsubsection xml:id="{xml_id}">\n'
            f'<title>{convert_inline(command["title"])}</title>\n'
            f'{convert_block(body)}\n'
            f'</subsubsection>'
        )

    return "\n\n".join(output)


def parse_subsections(text):
    commands = [
        c for c in find_structural_commands(text)
        if c["type"] == "subsection"
    ]

    if not commands:
        return convert_block(text)

    output = []

    intro = text[:commands[0]["start"]]

    if intro.strip():
        output.append(
            convert_block(intro)
        )

    for index, command in enumerate(commands):
        next_start = (
            commands[index + 1]["start"]
            if index + 1 < len(commands)
            else len(text)
        )

        body = text[
            command["content_start"]:
            next_start
        ]

        label, body = extract_leading_label(body)

        xml_id = (
            label_to_id(label)
            if label
            else "subsec-" + slugify(command["title"])
        )

        body_xml = parse_subsubsections(body)

        output.append(
            f'<subsection xml:id="{xml_id}">\n'
            f'<title>{convert_inline(command["title"])}</title>\n'
            f'{body_xml}\n'
            f'</subsection>'
        )

    return "\n\n".join(output)


def convert_document(text):
    text = strip_comments(text)

    section_match = re.search(
        r"\\section\{",
        text
    )

    if not section_match:
        raise RuntimeError(
            "No \\section{...} command found."
        )

    brace_start = section_match.end() - 1

    title, title_end = read_braced(
        text,
        brace_start
    )

    if title is None:
        raise RuntimeError(
            "Could not parse section title."
        )

    body = text[title_end:]

    label, body = extract_leading_label(body)

    section_id = (
        label_to_id(label)
        if label
        else "sec-" + slugify(title)
    )

    # --------------------------------------------------------
    # Split section introduction from subsections.
    #
    # PreTeXt sections cannot mix ordinary section-level
    # content followed directly by subsections.  Introductory
    # material must be placed inside <introduction>.
    # --------------------------------------------------------

    commands = [
        c for c in find_structural_commands(body)
        if c["type"] == "subsection"
    ]

    body_parts = []

    if commands:
        intro_source = body[:commands[0]["start"]]
        subsection_source = body[commands[0]["start"]:]

        intro_xml = convert_block(intro_source)

        if intro_xml.strip():
            body_parts.append(
                "<introduction>\n"
                + intro_xml
                + "\n</introduction>"
            )

        body_parts.append(
            parse_subsections(subsection_source)
        )

    else:
        body_parts.append(
            convert_block(body)
        )

    body_xml = "\n\n".join(
        part for part in body_parts
        if part.strip()
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n\n'
        f'<section xml:id="{section_id}">\n'
        f'<title>{convert_inline(title)}</title>\n\n'
        f'{body_xml}\n\n'
        f'</section>\n'
    )

# ============================================================
# SAFETY CHECKS
# ============================================================

def target_is_placeholder(path):
    if not path.exists():
        return True

    text = path.read_text(
        encoding="utf-8"
    )

    if PLACEHOLDER_TEXT in text:
        return True

    return False


def scan_remaining_latex(xml):
    patterns = [
        r"\\begin\{",
        r"\\end\{",
        r"\\section\{",
        r"\\subsection\{",
        r"\\subsubsection\{",
        r"\\item\b",
    ]

    found = []

    for pattern in patterns:
        if re.search(pattern, xml):
            found.append(pattern)

    return found


# ============================================================
# MAIN
# ============================================================

def main():
    if not LATEX_FILE.exists():
        raise SystemExit(
            f"Missing LaTeX file: {LATEX_FILE}"
        )

    if PTX_FILE.exists() and not target_is_placeholder(PTX_FILE):
        raise SystemExit(
            f"Refusing to overwrite non-placeholder file: {PTX_FILE}"
        )

    source = LATEX_FILE.read_text(
        encoding="utf-8"
    )

    xml = convert_document(source)

    remaining = scan_remaining_latex(xml)

    if remaining:
        print("WARNING: Unconverted LaTeX structures remain:")
        for item in remaining:
            print("  ", item)

    PTX_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if PTX_FILE.exists():
        backup = PTX_FILE.with_suffix(
            PTX_FILE.suffix + ".bak"
        )

        shutil.copy2(
            PTX_FILE,
            backup
        )

        print(
            f"Backup:    {backup}"
        )

    PTX_FILE.write_text(
        xml,
        encoding="utf-8"
    )

    print(
        f"Converted: {LATEX_FILE}"
    )

    print(
        f"Created:   {PTX_FILE}"
    )


if __name__ == "__main__":
    main()
