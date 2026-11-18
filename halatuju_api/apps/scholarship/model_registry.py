"""THE MODEL VERSION REGISTER (LL3): one entry per scoring model, and the fingerprint of its source.

Every decision HalaTuju records carries the version of the model that made it (the verdict engine's
`VERDICT_ENGINE_VERSION`, each document scorer's `MODEL_VERSION`, each parser's `PARSER_VERSION`).
A version is only worth recording if it moves whenever the model's answers can move. Nothing used
to make it move: a logic change could ship under the old number, and two different behaviours
would then be filed as one.

This module is the half that DESCRIBES each model:

* where its version constant lives;
* the source files that can change its answers (`files`, globs allowed);
* `pins`: single top-level definitions in OTHER files whose text the model depends on. The Gemini
  cascades are the main case. `halatuju/ai_registry.py` stores no model names (it reads the
  cascades live), so listing it alone would let a model switch ship with no bump; pinning
  `profile_engine.FLASH_25_CASCADE` closes that. A pin also takes in every same-module top-level
  name its definition uses, so a pinned list built from another list follows it. The guard walks
  a pin's imports like a listed file's (`pin_imports`), drops the pinned module's own version
  line, and refuses a module that changes a pinned name after defining it.

`model_versions/<model>.json` is the append-only log of the versions, each with the digest of the
source it was recorded against. `tests/test_model_versions.py` is the guard that fails when the
source moves and the version does not.

THE DIGEST does not depend on the Python version (production runs 3.11, a laptop may run 3.13),
so it is NOT an `ast.dump`, whose output changes between releases. For each file it reads the
text, makes line endings irrelevant, then removes comments, docstrings and the statement that sets
the model's own version constant (which must be one plain string on lines of its own, see
`version_assignment`), strips trailing spaces and drops blank lines. Lines INSIDE a
multi-line string (a prompt) are kept exactly, blank lines and trailing spaces included, because
there they are part of what the model is sent. Line numbers never enter the digest.

Pure standard library: no Django, so `python apps/scholarship/model_registry.py` (run from
`halatuju_api/`) prints every model's current version and digest without a database.
"""
import ast
import hashlib
import io
import json
import pathlib
import re
import tokenize

_APP = 'apps/scholarship'
_G = f'{_APP}/genuineness'
_AI_REGISTRY = 'halatuju/ai_registry.py'
_FLASH_25 = (f'{_APP}/profile_engine.py', 'FLASH_25_CASCADE')

#: Folder of the append-only version logs, relative to the API root.
VERSIONS_DIR = f'{_APP}/model_versions'

#: model key -> {constant: (file, name), files: [...], pins: [(file, name), ...]}.
#: Paths are relative to `halatuju_api/`. The key is also the log's file name.
MODELS = {
    'verdict_engine': {
        'constant': (f'{_APP}/verdict_engine.py', 'VERDICT_ENGINE_VERSION'),
        'files': [f'{_APP}/{name}.py' for name in (
            'verdict_engine', 'verdict_identity', 'verdict_academic', 'verdict_income_salary',
            'verdict_income_str', 'verdict_pathway', 'verdict_caps', 'verdict_ladder',
            'start_year', 'higher_results', 'requirements', 'document_snapshot')]
        + [f'{_G}/bands.py', f'{_APP}/income_engine/*.py'],
        'pins': [],
    },
    'results_doc': {
        'constant': (f'{_G}/results_doc.py', 'MODEL_VERSION'),
        # results_doc scores the results slip AND the offer letter; the offer rulings it reaches
        # lazily are part of its answer, so they are its files rather than a gap.
        'files': [f'{_G}/{name}.py' for name in (
            'results_doc', 'stpm_doc', 'matric_poly_doc', 'bands', 'epf_app_doc',
            'offer_signatures', 'offer_rulings', 'offer_issuers', 'offer_reading', 'offer_text',
            'offer_confirmations', 'offer_confirm_checks', 'offer_agency')] + [_AI_REGISTRY],
        'pins': [_FLASH_25] + [(f'{_APP}/results_kind.py', name) for name in (
            'detect', 'prints_polytechnic', '_NOT_ISSUERS')],
    },
    'salary_doc': {
        'constant': (f'{_G}/salary_doc.py', 'MODEL_VERSION'),
        'files': [f'{_G}/salary_doc.py', f'{_G}/declaration_doc.py'],
        'pins': [(f'{_G}/results_doc.py', '_any_token'),
                 (f'{_G}/results_doc.py', '_norm_fold_upper_alnum')],
    },
    'electricity_doc': {
        'constant': (f'{_G}/electricity_doc.py', 'MODEL_VERSION'),
        'files': [f'{_G}/electricity_doc.py'],
        'pins': [(f'{_G}/results_doc.py', '_any_token'),
                 (f'{_G}/results_doc.py', '_norm_fold_upper_alnum')],
    },
    'water_doc': {
        'constant': (f'{_G}/water_doc.py', 'MODEL_VERSION'),
        'files': [f'{_G}/water_doc.py'],
        'pins': [(f'{_G}/results_doc.py', '_any_token'),
                 (f'{_G}/results_doc.py', '_norm_fold_upper_alnum')],
    },
    'school_leaving_doc': {
        'constant': (f'{_G}/school_leaving_doc.py', 'MODEL_VERSION'),
        'files': [f'{_G}/school_leaving_doc.py'],
        'pins': [(f'{_G}/results_doc.py', '_any_token'),
                 (f'{_G}/results_doc.py', '_norm_fold_upper_alnum'),
                 (f'{_G}/results_doc.py', 'misfiled_as'),
                 # what misfiled_as reaches in other files (LL3 review: pins follow their imports)
                 (f'{_G}/bands.py', 'GENUINE_MIN'),
                 (f'{_G}/stpm_doc.py', 'STPM_LISTS')],
    },
    # LL3 phase 2: the two AI genuineness reads that had no version. Both call Gemini on the
    # 2.5 Flash cascade, so they carry the AI register and the cascade pin like sample_stamp.
    'ic': {
        'constant': (f'{_G}/ic.py', 'MODEL_VERSION'),
        'files': [f'{_G}/ic.py', _AI_REGISTRY],
        'pins': [_FLASH_25],
    },
    'supporting_doc': {
        'constant': (f'{_G}/supporting_doc.py', 'MODEL_VERSION'),
        'files': [f'{_G}/supporting_doc.py', _AI_REGISTRY],
        'pins': [_FLASH_25],
    },
    'sample_stamp': {
        'constant': (f'{_G}/sample_stamp.py', 'SAMPLE_CHECK_VERSION'),
        'files': [f'{_G}/sample_stamp.py', _AI_REGISTRY],
        'pins': [_FLASH_25, (f'{_G}/bands.py', 'stored_authenticity')],
    },
    'offer_reader': {
        'constant': (f'{_APP}/offer_reader.py', 'OFFER_READER_VERSION'),
        'files': [f'{_APP}/offer_reader.py', _AI_REGISTRY],
        'pins': [(f'{_APP}/profile_engine.py', 'MODEL_CASCADE'),
                 (f'{_APP}/vision/gemini_read.py', '_WARNING_VOICE'),
                 (f'{_APP}/vision/sanitize.py', '_sanitize_extracted_fields'),
                 (f'{_APP}/vision/sanitize.py', '_drop_expected_warnings'),
                 (f'{_APP}/offer_course_match.py', 'COURSE_CODE_RE'),
                 (f'{_APP}/offer_course_match.py', '_LOCAL_CODE_RE'),
                 (f'{_APP}/offer_ic.py', 'guard_nric'),
                 # what the pins above reach in other files (LL3 review: pins follow their imports)
                 (f'{_APP}/vision/judge.py', '_strip_name_label'),
                 (f'{_APP}/name_order.py', 'patronymic_reversed')]
        + [(f'{_APP}/vision/names.py', name) for name in (
            'name_match', 'nric_close', 'nric_dob_agrees', 'nric_match', '_split_glued_markers',
            'canonical_name_tokens')],
    },
    'offer_parse': {
        'constant': (f'{_APP}/offer_parse.py', 'PARSER_VERSION'),
        'files': [f'{_APP}/offer_parse.py', f'{_APP}/offer_parse_families.py'],
        'pins': [(f'{_APP}/vision/sanitize.py', '_normalise_reporting_date'),
                 (f'{_APP}/card_display.py', 'looks_like_date'),
                 (f'{_APP}/card_display.py', 'looks_like_clause_number')],
    },
    'stpm_parse': {
        'constant': (f'{_APP}/stpm_parse.py', 'PARSER_VERSION'),
        'files': [f'{_APP}/stpm_parse.py', f'{_APP}/stpm_columns.py'],
        'pins': [(f'{_APP}/academic_engine.py', '_group_rows')],
    },
    'matric_parse': {
        'constant': (f'{_APP}/matric_parse.py', 'PARSER_VERSION'),
        'files': [f'{_APP}/matric_parse.py'],
        'pins': [(f'{_APP}/poly_diploma_parse.py', 'CONNECTORS'),
                 (f'{_APP}/academic_engine.py', '_group_rows')]     # stpm_parse._rows_of's lazy import
        + [(f'{_APP}/stpm_parse.py', name) for name in (
            'GRADE_POINTS', '_NRIC_RE', '_after', '_clean_name', '_letters', '_rows_of')],
    },
    'poly_diploma_parse': {
        'constant': (f'{_APP}/poly_diploma_parse.py', 'PARSER_VERSION'),
        'files': [f'{_APP}/poly_diploma_parse.py'],
        'pins': [],
    },
}


# --- reading -----------------------------------------------------------------------------------

def _model_text(root, rel):
    """The file's text with a BOM dropped and every line ending made `\\n`."""
    raw = (pathlib.Path(root) / rel).read_bytes().decode('utf-8')
    return raw.lstrip('﻿').replace('\r\n', '\n').replace('\r', '\n')


def expand_model_files(root, patterns):
    """`files` with globs expanded, as sorted POSIX paths relative to `root`."""
    root = pathlib.Path(root)
    out = set()
    for pat in patterns:
        if any(ch in pat for ch in '*?['):
            out.update(p.relative_to(root).as_posix() for p in root.glob(pat) if p.is_file())
        else:
            out.add(pat)
    return sorted(out)


# --- cleaning ----------------------------------------------------------------------------------

def _docstring_nodes(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                yield body[0]


def _assigns_name(node, names):
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    else:
        return False
    return any(isinstance(t, ast.Name) and t.id in names for t in targets)


def version_assignment(tree, name):
    """The ONE top-level statement that sets the version constant `name`. Because the digest drops
    that statement's rows whole, it must be safe to drop: exactly one top-level assignment, of a
    plain string, to that name alone, with no other statement on its rows. Anything else could hide
    logic (`MODEL_VERSION = '1.0.0'; THRESHOLD = 0.70`) or a second value, so it raises ValueError."""
    hits = [node for node in tree.body if _assigns_name(node, (name,))]
    if len(hits) != 1:
        raise ValueError(f'{name} must be set exactly once at the top level of the file; found '
                         f'{len(hits)}. The version guard cannot tell which one counts.')
    node = hits[0]
    plain = (isinstance(node, ast.Assign) and len(node.targets) == 1) or isinstance(node, ast.AnnAssign)
    if not (plain and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
        raise ValueError(f"{name} must be a plain string set on its own (like {name} = '1.0.0'), so "
                         'that dropping it from the digest drops nothing else.')
    for other in ast.walk(tree):
        if (isinstance(other, ast.stmt) and other is not node
                and other.lineno <= node.end_lineno and other.end_lineno >= node.lineno):
            raise ValueError(f'{name} shares a line with other code (row {other.lineno}). Put the '
                             'version on lines of its own: the digest drops those lines whole.')
    return node


def _string_rows(text):
    """Rows that sit INSIDE a multi-line string: (start_row, end_row) of each such string token.
    Python 3.12+ splits an f-string into FSTRING_START ... FSTRING_END; 3.11 gives one STRING
    token. Both describe the same span, so the result is the same on either."""
    f_start = getattr(tokenize, 'FSTRING_START', None)
    f_end = getattr(tokenize, 'FSTRING_END', None)
    spans, open_rows = [], []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if f_start is not None and tok.type == f_start:
            open_rows.append(tok.start[0])
        elif f_end is not None and tok.type == f_end and open_rows:
            row = open_rows.pop()
            if not open_rows and tok.end[0] > row:
                spans.append((row, tok.end[0]))
        elif tok.type == tokenize.STRING and not open_rows and tok.end[0] > tok.start[0]:
            spans.append((tok.start[0], tok.end[0]))
    return spans


def _comment_starts(text):
    """row -> character column where that row's comment starts."""
    return {tok.start[0]: tok.start[1]
            for tok in tokenize.generate_tokens(io.StringIO(text).readline)
            if tok.type == tokenize.COMMENT}


def clean_model_source(text, drop_names=(), keep_rows=None):
    """The text a model digest is taken over (see the module docstring).

    `text` already has `\\n` line endings. `drop_names` are top-level version names whose one
    assignment is removed (`version_assignment` refuses an unsafe one). `keep_rows`, when given,
    keeps only those 1-based rows (a pin's statements); everything else about the cleaning is the
    same.
    """
    tree = ast.parse(text)
    lines = [ln.encode('utf-8') for ln in text.split('\n')]
    cut = []                                   # (row1, byte_col1, row2, byte_col2), 1-based rows
    for node in _docstring_nodes(tree):
        cut.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset))
    for name in sorted(set(drop_names)):
        node = version_assignment(tree, name)
        cut.append((node.lineno, 0, node.end_lineno, len(lines[node.end_lineno - 1])))
    text_lines = text.split('\n')
    for row, col in _comment_starts(text).items():
        byte_col = len(text_lines[row - 1][:col].encode('utf-8'))
        cut.append((row, byte_col, row, len(lines[row - 1])))
    cut_rows = set()
    for r1, c1, r2, c2 in sorted(cut, reverse=True):
        head, tail = lines[r1 - 1][:c1], lines[r2 - 1][c2:]
        lines[r1 - 1:r2] = [head + tail] + [b''] * (r2 - r1)
        if r2 > r1:
            cut_rows.update(range(r1, r2 + 1))
    verbatim = set()
    for r1, r2 in _string_rows(text):
        if r1 not in cut_rows:
            verbatim.update(range(r1, r2))     # the string's last row is ordinary code after it
    out = []
    for row, raw in enumerate(lines, 1):
        if keep_rows is not None and row not in keep_rows:
            continue
        line = raw.decode('utf-8')
        if row in verbatim:
            out.append(line)
        elif line.strip():
            out.append(line.rstrip())
    return '\n'.join(out)


# --- pins --------------------------------------------------------------------------------------

def _defined_names(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    targets = node.targets if isinstance(node, ast.Assign) else (
        [node.target] if isinstance(node, ast.AnnAssign) else [])
    return {t.id for t in targets if isinstance(t, ast.Name)}


#: A version constant's name (`MODEL_VERSION`, `PARSER_VERSION`, ...).
VERSION_NAME = re.compile(r'(^|_)VERSION$')

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _block_bound(tree):
    """Names bound at import time by a statement `_defined_names` does not see: inside a top-level
    if / try / with / for block (`try: LIMIT = 0.7`), or a top-level for / with target. Top-level
    imports are left out: a pin's module imports are walked as its dependencies instead."""
    top, bound = {id(node) for node in tree.body}, set()
    for node in _module_level(tree):
        targets = []
        if isinstance(node, _DEFS):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in top:
            bound.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
        for target in targets:            # C = / C, D = / for C in: binds; C[k] = does not
            bound.update(n.id for n in ast.walk(target)
                         if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store))
    return bound


def _pin_closure(tree, rel, name):
    """(names, nodes): `name` plus every same-module top-level name its definition uses,
    transitively, and the top-level statements that define them. A used name bound only inside
    a top-level block is refused (ValueError): the pin would not read it, so changing it would
    not move the digest."""
    homes = {}
    for node in tree.body:
        for defined in _defined_names(node):
            homes.setdefault(defined, []).append(node)
    if name not in homes:
        raise KeyError(f'{rel} defines no top-level {name!r}')
    block_only = _block_bound(tree) - set(homes)
    wanted, todo, nodes = set(), [name], []
    while todo:
        current = todo.pop()
        if current in block_only:
            raise ValueError(
                f'{rel}: the pin on {name!r} uses {current!r}, which is set only inside an if / '
                'try / with / for block. A pin reads only top-level definitions, so a change to it '
                'would not move the digest. Define it at the top level, or list the file in the '
                "model's files instead of pinning.")
        if current in wanted or current not in homes:
            continue
        wanted.add(current)
        for node in homes[current]:
            nodes.append(node)
            todo.extend(n.id for n in ast.walk(node) if isinstance(n, ast.Name))
    return wanted, nodes


def _module_level(tree):
    """Every statement that runs at import time: the top level and the bodies of top-level
    if / try / with / for blocks, but never the inside of a function or class."""
    todo = list(tree.body)
    while todo:
        node = todo.pop()
        yield node
        if not isinstance(node, _DEFS):
            todo.extend(child for child in ast.iter_child_nodes(node) if isinstance(child, ast.stmt))
            for handler in getattr(node, 'handlers', []):
                todo.extend(handler.body)


def _base_name(node):
    while isinstance(node, (ast.Subscript, ast.Attribute, ast.Starred)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _touched_names(node):
    """Names a module-level statement rebinds, augments, item- or attribute-assigns, deletes or
    calls a method on. Its own nested statements are visited separately by `_module_level`."""
    targets = []
    if isinstance(node, (ast.Assign, ast.Delete)):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        targets = [item.optional_vars for item in node.items if item.optional_vars is not None]
    touched = set()
    while targets:
        target = targets.pop()
        if isinstance(target, (ast.Tuple, ast.List)):
            targets.extend(target.elts)
        else:
            touched.add(_base_name(target))   # C, C[k], C.attr, *C  ->  C
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        touched.update((a.asname or a.name).split('.')[0] for a in node.names)
    if isinstance(node, _DEFS):
        touched.add(node.name)               # a second definition; its body is not module-level
        return touched
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            continue
        for part in ast.walk(child):
            if isinstance(part, ast.NamedExpr):
                touched.add(part.target.id)
            elif isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute):
                touched.add(_base_name(part.func.value))
    touched.discard(None)
    return touched


def _refuse_later_changes(tree, rel, names, nodes):
    """A pin covers a definition, not what the module does to it afterwards: `C += [...]`,
    `C.insert(...)`, `C[k] = ...` or a `C = ...` inside an if / try block would change the answer
    and leave the digest alone. So any such statement on a pinned name raises ValueError. (A
    second plain top-level `C = ...` is a definition: the pin already reads it.) Import-time,
    module-level statements ONLY: a change inside a function that is then called, a `global`
    rebind, an alias (`A = C; A.append(...)`) or globals()/setattr is not seen (a recorded gap)."""
    own = {id(node) for node in nodes}
    for node in _module_level(tree):
        if id(node) in own:
            continue
        clash = sorted(_touched_names(node) & names)
        if clash:
            raise ValueError(
                f'{rel} row {node.lineno} changes {", ".join(clash)} after its definition. A pin '
                'reads only the definition, so this change would not move the digest. Fold it into '
                'the definition, or list the file in the model\'s files instead of pinning.')


def pinned_model_text(root, rel, name):
    """The cleaned text of the top-level statements defining `name` in `rel`, plus (transitively)
    every same-module top-level name those statements use. Raises KeyError if `name` is not
    defined at the top level of `rel`, so a pin cannot go quietly empty, and ValueError if the
    module changes a pinned name after defining it. The pinned module's OWN version constants are
    dropped (as in its own digest): its version is not this model's logic, and keeping it would
    turn this model red at every bump of that other model."""
    text = _model_text(root, rel)
    tree = ast.parse(text)
    names, nodes = _pin_closure(tree, rel, name)
    _refuse_later_changes(tree, rel, names, nodes)
    versions = {n for n in names if VERSION_NAME.search(n)}
    rows = set()
    for node in nodes:
        first = min([node.lineno] + [d.lineno for d in getattr(node, 'decorator_list', [])])
        rows.update(range(first, node.end_lineno + 1))
    return clean_model_source(text, drop_names=versions, keep_rows=rows)


# --- the digest --------------------------------------------------------------------------------

def model_digest(root, key):
    """sha256 over the model's sorted (label, cleaned text) pairs. A file's label is its path; a
    pin's is `pin:<path>:<name>`. Each part is length-prefixed so two parts cannot run together."""
    spec = MODELS[key]
    const_file, const_name = spec['constant']
    parts = []
    for rel in expand_model_files(root, spec['files']):
        drop = (const_name,) if rel == const_file else ()
        try:
            parts.append((rel, clean_model_source(_model_text(root, rel), drop_names=drop)))
        except ValueError as exc:
            raise ValueError(f'{rel}: {exc}') from exc
    for rel, name in spec['pins']:
        parts.append((f'pin:{rel}:{name}', pinned_model_text(root, rel, name)))
    h = hashlib.sha256()
    for label, body in sorted(parts):
        for piece in (label, body):
            data = piece.encode('utf-8')
            h.update(str(len(data)).encode('ascii') + b':' + data)
    return h.hexdigest()


def read_model_version(root, key):
    """The model's version, read statically from its constant (no import, so no Django)."""
    rel, name = MODELS[key]['constant']
    try:
        return version_assignment(ast.parse(_model_text(root, rel)), name).value.value
    except ValueError as exc:
        raise ValueError(f'{rel}: {exc}') from exc


def _refuse_duplicate_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f'duplicate key {k!r}: an append-only log never repeats a version')
        seen[k] = v
    return seen


def load_version_log(root, key):
    """`model_versions/<key>.json`, in file order. A repeated version is an error, not a merge."""
    path = pathlib.Path(root) / VERSIONS_DIR / f'{key}.json'
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_refuse_duplicate_keys)


# --- the dependency walk -----------------------------------------------------------------------

def _module_file(root, dotted):
    base = pathlib.Path(root).joinpath(*dotted.split('.'))
    if base.with_suffix('.py').is_file():
        return base.with_suffix('.py').relative_to(root).as_posix()
    if (base / '__init__.py').is_file():
        return (base / '__init__.py').relative_to(root).as_posix()
    return None


def _package_of(rel):
    parts = rel[:-3].split('/')
    return parts[:-1]                          # `pkg/__init__` and `pkg/mod` both live in `pkg`


def _import_nodes(nodes):
    for top in nodes:
        for node in ast.walk(top):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                yield node


def _resolve_imports(root, rel, imports, scope, only_local=None):
    """The `apps.*` (target file, name) pairs of the `imports` statements. `scope` is where a
    module imported whole (`from pkg import mod`) has its `mod.<attr>` uses read; `only_local`,
    when given, keeps only the imports that bind one of those local names."""
    root = pathlib.Path(root)
    found, as_module = set(), {}
    for node in imports:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if only_local is not None and (alias.asname or alias.name.split('.')[0]) not in only_local:
                    continue
                target = _module_file(root, alias.name) if alias.name.startswith('apps.') else None
                if target:
                    found.add((target, '*'))
            continue
        if node.level:
            pkg = _package_of(rel)[:len(_package_of(rel)) - (node.level - 1)]
            dotted = '.'.join(pkg + ([node.module] if node.module else []))
        else:
            dotted = node.module or ''
        if not dotted.startswith('apps.'):
            continue
        for alias in node.names:
            if only_local is not None and (alias.asname or alias.name) not in only_local | {'*'}:
                continue
            sub = _module_file(root, f'{dotted}.{alias.name}') if alias.name != '*' else None
            if sub:
                as_module[alias.asname or alias.name] = sub
            else:
                target = _module_file(root, dotted)
                if target:
                    found.add((target, alias.name))
    for local, target in as_module.items():
        attrs = {n.attr for top in scope for n in ast.walk(top) if isinstance(n, ast.Attribute)
                 and isinstance(n.value, ast.Name) and n.value.id == local}
        found.update((target, attr) for attr in (attrs or {'*'}))
    return found


def model_imports(root, rel):
    """Every `apps.*` dependency of one file, as sorted (target file, name) pairs. `name` is the
    imported name, `*` for a star import or a module used whole, or `<attr>` for each `mod.<attr>`
    used after `from pkg import mod`. Lazy imports inside functions count the same."""
    tree = ast.parse(_model_text(root, rel))
    return sorted(_resolve_imports(root, rel, _import_nodes([tree]), [tree]))


def pin_imports(root, rel, name):
    """The same walk over a PIN: every `apps.*` dependency of the pinned closure (the statements
    `pinned_model_text` reads). That is the imports inside those statements (lazy ones), plus each
    import at the top of the module whose name the closure uses. A pinned helper that reaches into
    another file is then caught like a listed file's import."""
    tree = ast.parse(_model_text(root, rel))
    names, nodes = _pin_closure(tree, rel, name)
    used = {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}
    found = _resolve_imports(root, rel, _import_nodes(nodes), nodes)
    module_level = [n for n in _module_level(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    found |= _resolve_imports(root, rel, module_level, nodes, only_local=used)
    return sorted(found)


def _main(root):
    for key in MODELS:
        print(f'{key:20} {read_model_version(root, key):14} {model_digest(root, key)}')


if __name__ == '__main__':                     # pragma: no cover — a printer for the engineer
    _main(pathlib.Path(__file__).resolve().parents[2])
