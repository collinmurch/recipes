"""The recipes command line."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from . import render, schema_org, yamlio
from .collection import (
    COURSES,
    DIRS,
    PLANS,
    SCHEMA,
    Collection,
    Problem,
    is_date,
    is_slug,
    open_collection,
    slugify,
)
from .vocab import humanize


class Exit(Exception):
    def __init__(self, message: str = "", code: int = 1):
        super().__init__(message)
        self.code = code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "run"):
        parser.print_help()
        return 0
    try:
        args.run(open_collection(args.source), args)
        return 0
    except Exit as e:
        if str(e):
            print(e, file=sys.stderr)
        return e.code
    except (RuntimeError, ValueError, OSError) as e:
        print(e, file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    # Global options work before or after the command. Each parser needs its own
    # copies, and the subcommands' copies set a value only when given.
    def add_globals(p, source, as_json):
        p.add_argument("--source", default=source, help="a repo folder, a built index.json (or its folder), or a URL")
        p.add_argument("--json", action="store_true", default=as_json, help="print JSON (find, show, grocery)")

    common = argparse.ArgumentParser(add_help=False)
    add_globals(common, argparse.SUPPRESS, argparse.SUPPRESS)
    parser = argparse.ArgumentParser(
        prog="recipes",
        description="Search, plan, and write our recipes. Reads the repo when run inside it, "
        "and the published index anywhere else.",
    )
    add_globals(parser, None, False)
    commands = parser.add_subparsers(title="commands", metavar="<command>")

    def command(name, run, help, **kwargs):
        sub = commands.add_parser(name, parents=[common], help=help, description=help, **kwargs)
        sub.set_defaults(run=run)
        return sub

    find = command("find", cmd_find, "search recipes and drinks")
    find.add_argument("words", nargs="*", help="words to match in titles, tags, and ingredients")
    find.add_argument("--course", choices=COURSES)
    find.add_argument("--cuisine")
    find.add_argument("--protein", help='a protein, or "none"')
    find.add_argument("--tag")
    find.add_argument("--uses", action="append", default=[], metavar="INGREDIENT", help="repeatable")
    find.add_argument("--max-time", type=int, metavar="MINUTES")
    find.add_argument("--not-since", type=iso_date, metavar="DATE", help="not cooked on or after DATE")
    find.add_argument("--kind", choices=tuple(DIRS))

    show = command("show", cmd_show, "show a recipe, or preview a draft file")
    show.add_argument("target", metavar="name|file")
    show.add_argument("--servings", type=positive)

    export = command("export", cmd_export, "print recipes as schema.org Recipe JSON-LD, for other apps")
    export.add_argument("targets", nargs="*", metavar="name|file")
    export.add_argument("--all", action="store_true", help="every recipe and drink, as one @graph")

    grocery = command("grocery", cmd_grocery, "one shopping list for several recipes")
    grocery.add_argument("picks", nargs="*", metavar="name[:servings]")
    grocery.add_argument("--plan", metavar="ID", help="use a plan's uncooked meals")

    validate = command("validate", cmd_validate, "check drafts, or the whole repo")
    validate.add_argument("files", nargs="*")

    save = command("save", cmd_save, "check drafts together and file them (repo only)")
    save.add_argument("files", nargs="+")
    save.add_argument("--replace", action="store_true", help="overwrite a recipe with the same name")

    vocab = command("vocab", None, "look up or edit ingredient names")
    actions = vocab.add_subparsers(title="actions", metavar="<action>", required=True)
    vfind = actions.add_parser("find", parents=[common], help="look up names, with close matches")
    vfind.add_argument("names", nargs="+")
    vfind.set_defaults(run=cmd_vocab_find)
    vlist = actions.add_parser("list", parents=[common], help="list the vocab")
    vlist.add_argument("section", nargs="?")
    vlist.set_defaults(run=cmd_vocab_list)
    vadd = actions.add_parser("add", parents=[common], help="add ingredients (repo only)")
    vadd.add_argument("names", nargs="+")
    vadd.add_argument("--section", required=True)
    vadd.add_argument("--aka", action="append", default=[], metavar="ALIAS", help="repeatable")
    vadd.add_argument("--protein")
    vadd.set_defaults(run=cmd_vocab_add)
    valias = actions.add_parser("alias", parents=[common], help="add other names for an entry (repo only)")
    valias.add_argument("name")
    valias.add_argument("aliases", nargs="+")
    valias.set_defaults(run=cmd_vocab_alias)

    plan = command("plan", cmd_plan, "start or add to a plan (repo only)")
    plan.add_argument("picks", nargs="*", metavar="name[:servings]")
    plan.add_argument("--start", type=iso_date, help="the plan's first day (default: this Monday)")
    plan.add_argument("--name", type=slug, help="for a one-off plan, like dinner-party")

    cooked = command("cooked", cmd_cooked, "mark a meal cooked (repo only)")
    cooked.add_argument("name")
    cooked.add_argument("--date", type=iso_date, help="default: today")
    cooked.add_argument("--plan", metavar="ID")

    build = command("build", cmd_build, "check everything and write the site bundle (repo only)")
    build.add_argument("dir", nargs="?", default="dist")
    return parser


def iso_date(value: str) -> str:
    if not is_date(value):
        raise argparse.ArgumentTypeError("should be YYYY-MM-DD")
    return value


def slug(value: str) -> str:
    if not is_slug(value):
        raise argparse.ArgumentTypeError("should be lowercase words joined by hyphens")
    return value


def positive(value: str) -> int | float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("should be a number") from None
    if number <= 0:
        raise argparse.ArgumentTypeError("should be above zero")
    return int(number) if number.is_integer() else number


def out(text: str = "") -> None:
    sys.stdout.write(text.rstrip("\n") + "\n")


def cmd_find(c: Collection, args) -> None:
    warn_if_stale(c)
    uses = []
    for written in args.uses:
        entry = c.vocab.lookup(written)
        if not entry:
            raise Exit(f'"{written}" is not in the vocab{hint(c.vocab.suggest(written))}')
        uses.append(entry.name)
    words = [w.lower() for w in args.words]

    def matches(r: dict) -> bool:
        names = {i["name"] for g in r["ingredients"] for i in g["items"] if i["name"]}
        if args.kind and r["kind"] != args.kind:
            return False
        if args.course and r.get("course") != args.course:
            return False
        if args.cuisine and r.get("cuisine") != args.cuisine:
            return False
        if args.protein and (r["proteins"] if args.protein == "none" else args.protein not in r["proteins"]):
            return False
        if args.tag and args.tag not in r.get("tags", []):
            return False
        if args.max_time and not (r.get("time_total") or 0) <= args.max_time:
            return False
        if args.not_since and r.get("last_cooked") and r["last_cooked"] >= args.not_since:
            return False
        if not all(u in names for u in uses):
            return False
        haystack = " ".join(
            [
                r["slug"],
                r.get("title", ""),
                r.get("description", ""),
                r.get("cuisine", ""),
                *r.get("tags", []),
                *map(humanize, names),
            ]
        ).lower()
        return all(w in haystack for w in words)

    results = [r for r in c.recipes if matches(r)]
    if args.json:
        return out(json.dumps([summary(r) for r in results], indent=2))
    if not results:
        return out("No matches.")
    out(
        render.table(
            ["name", "title", "course", "cuisine", "protein", "time", "leftovers", "last cooked"],
            [
                [
                    r["slug"],
                    r.get("title"),
                    r.get("course"),
                    r.get("cuisine"),
                    ", ".join(r["proteins"]),
                    render.duration(r.get("time_total")),
                    r.get("leftovers"),
                    r.get("last_cooked") or "never",
                ]
                for r in results
            ],
        )
    )


def summary(r: dict) -> dict:
    trimmed = {k: v for k, v in r.items() if k not in ("ingredients", "sections", "cookware")}
    trimmed["ingredients"] = [i["name"] or i["text"] for g in r["ingredients"] for i in g["items"]]
    return trimmed


def cmd_show(c: Collection, args) -> None:
    r = resolve(c, args.target, allow_file=True)
    out(json.dumps(r, indent=2) if args.json else render.recipe(r, args.servings))


def cmd_export(c: Collection, args) -> None:
    if args.all == bool(args.targets):
        raise Exit("export needs recipe names or --all")
    if args.all:
        document = schema_org.graph(c.recipes)
    else:
        records = [resolve(c, target, allow_file=True) for target in args.targets]
        document = schema_org.recipe(records[0]) if len(records) == 1 else schema_org.graph(records)
    out(json.dumps(document, indent=2, ensure_ascii=False))


def cmd_grocery(c: Collection, args) -> None:
    warn_if_stale(c)
    if args.plan:
        plan = c.plan(args.plan)
        if not plan:
            raise Exit(f'no plan "{args.plan}"')
        picks = [(resolve(c, m["recipe"]), m.get("servings")) for m in plan["meals"] if not m.get("cooked")]
        extras, title = plan["extras"], plan_title(plan)
    elif args.picks:
        picks = [(resolve(c, name), servings) for name, servings in map(parse_pick, args.picks)]
        extras, title = [], ", ".join(r.get("title", r["slug"]) for r, _ in picks)
    else:
        raise Exit("grocery needs recipe names or --plan <id>")
    sections = render.groceries(picks, c.vocab, extras)
    out(json.dumps(sections, indent=2) if args.json else render.grocery_list(sections, f"Groceries: {title}"))


def cmd_validate(c: Collection, args) -> None:
    if c.mode == "index" and not c.current:
        raise Exit(
            f"the published index is format {c.index.get('schema')} but this skill is format {SCHEMA}; "
            "download the latest skill and try again",
            2,
        )
    if args.files:
        problems = [p for checked in check_files(c, args.files) for p in checked.problems]
        label = count(len(args.files), "file")
    else:
        repo_root(c, "validate with no files")
        problems = c.problems
        label = f"{count(len(c.recipes), 'recipe')}, {count(len(c.plans), 'plan')}"
    report(problems, label)
    if any(p.level == "error" for p in problems):
        raise Exit()


def cmd_save(c: Collection, args) -> None:
    root = repo_root(c, "save")
    checked = check_files(c, args.files)
    if any("meals" in item.record for item in checked):
        raise Exit("save is for recipes; write plans with plan and cooked")
    problems = [p for item in checked for p in item.problems]
    moves = []
    for item in checked:
        dest = root / DIRS[item.record["kind"]] / f"{slugify(item.record.get('title', ''))}.cook"
        if dest != item.path.resolve() and dest.exists() and not args.replace:
            problems.append(Problem(item.label, f"{c.relative(dest)} already exists; pass --replace to overwrite it"))
        moves.append((item, dest))
    if any(p.level == "error" for p in problems):
        report(problems, count(len(args.files), "file"))
        raise Exit("nothing saved")
    report(problems)
    for item, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = item.path.read_text().rstrip() + "\n"
        moved = dest != item.path.resolve() and c.filed(item.path)
        dest.write_text(text)
        if moved:
            item.path.unlink()
            old = item.path.stem
            out(f'moved {moved} to {c.relative(dest)}; update any pairs or plans that named "{old}"')
        else:
            out(f"saved {c.relative(dest)}")


def cmd_vocab_find(c: Collection, args) -> None:
    for name in args.names:
        entry = c.vocab.lookup(name)
        if entry:
            extra = f", {entry.protein}" if entry.protein else ""
            out(f"{name} → {entry.name} ({entry.section}{extra})")
        else:
            out(f"{name}: not in the vocab{hint(c.vocab.suggest(name)) or '; no close matches'}")


def cmd_vocab_list(c: Collection, args) -> None:
    sections = [s for s in c.vocab.sections if not args.section or s.name == args.section]
    if not sections:
        raise Exit(f'no section "{args.section}"')
    for section in sections:
        out(f"{section.name}: {', '.join(section.items) or '(empty)'}")


def cmd_vocab_add(c: Collection, args) -> None:
    repo_root(c, "vocab add")
    if len(args.names) > 1 and args.aka:
        raise Exit("--aka applies to one name at a time")
    for name in args.names:
        added = c.vocab.add(name, args.section, args.aka, args.protein)
        out(f"added {added} to {args.section}")
    save_vocab(c)


def cmd_vocab_alias(c: Collection, args) -> None:
    repo_root(c, "vocab alias")
    target = c.vocab.alias(args.name, args.aliases)
    out(f"{', '.join(args.aliases)} → {target}")
    save_vocab(c)


def save_vocab(c: Collection) -> None:
    (repo_root(c, "editing the vocab") / "vocab.yaml").write_text(c.vocab.stringify())


def cmd_plan(c: Collection, args) -> None:
    repo_root(c, "plan")
    start = args.start or monday(date.today().isoformat())
    plan_id = f"{start}-{args.name}" if args.name else start
    plan = PlanFile.read(c, plan_id)
    for name, servings in map(parse_pick, args.picks):
        resolve(c, name)
        plan.meals.append({"recipe": name, "servings": servings} if servings else {"recipe": name})
    plan.write()
    out(f"wrote {c.relative(plan.path)}")
    picks = [(resolve(c, m["recipe"]), m.get("servings")) for m in plan.meals if not m.get("cooked")]
    if picks:
        sections = render.groceries(picks, c.vocab, plan.data.get("extras", []))
        out()
        out(render.grocery_list(sections, f"Groceries: {plan_title({**plan.data, 'id': plan_id})}"))


def cmd_cooked(c: Collection, args) -> None:
    repo_root(c, "cooked")
    resolve(c, args.name)
    when = args.date or date.today().isoformat()
    # The given plan, or else the latest plans that had started by then.
    started = [p["id"] for p in reversed(c.plans) if p["start"] and p["start"] <= when]
    candidates = [args.plan] if args.plan else started
    for plan_id in candidates:
        plan = PlanFile.read(c, plan_id)
        meal = next((m for m in plan.meals if m.get("recipe") == args.name and not m.get("cooked")), None)
        if meal:
            meal["cooked"] = when
            plan.write()
            return out(f"marked {args.name} cooked on {when} in {c.relative(plan.path)}")
    plan = PlanFile.read(c, args.plan or monday(when))
    plan.meals.append({"recipe": args.name, "cooked": when})
    plan.write()
    out(f"added {args.name}, cooked on {when}, to {c.relative(plan.path)}")


def cmd_build(c: Collection, args) -> None:
    root = repo_root(c, "build")
    if any(p.level == "error" for p in c.problems):
        report(c.problems, "build")
        raise Exit("not built")
    target = Path(args.dir).resolve()
    for folder in ("sources", "jsonld"):
        shutil.rmtree(target / folder, ignore_errors=True)
        (target / folder).mkdir(parents=True)
    for r in c.recipes:
        shutil.copyfile(root / r["path"], target / "sources" / f"{r['slug']}.cook")
        write_json(target / "jsonld" / f"{r['slug']}.json", schema_org.recipe(r))
    write_json(target / "index.json", c.index)
    out(f"wrote {args.dir}/index.json, plus sources/ and jsonld/ for {count(len(c.recipes), 'recipe')}")


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")


@dataclass
class Checked:
    path: Path
    label: str
    record: dict
    problems: list[Problem]


def check_files(c: Collection, files: list[str]) -> list[Checked]:
    """Checks files: filed ones by the repo's own results, drafts together."""
    checked, drafts = [], []
    for file in files:
        path = Path(file)
        if not path.is_file():
            raise Exit(f"no such file: {file}")
        filed = c.filed(path)
        known = next((x for x in (*c.recipes, *c.plans) if x["path"] == filed), None) if filed else None
        if filed and known:
            checked.append(Checked(path, filed, known, [p for p in c.problems if p.path == filed]))
        else:
            drafts.append((path, filed or file))
    results = c.check_drafts([(label, path.read_text()) for path, label in drafts])
    checked += [
        Checked(path, label, record, problems)
        for (path, label), (record, problems) in zip(drafts, results, strict=True)
    ]
    return checked


def resolve(c: Collection, target: str, allow_file: bool = False) -> dict:
    if r := c.recipe(target):
        return r
    if allow_file and (target.endswith(".cook") or Path(target).is_file()):
        [item] = check_files(c, [target])
        report(item.problems, stream=sys.stderr)
        return item.record
    close = [s for s in c.by_slug if target in s or s in target]
    raise Exit(f'no recipe named "{target}"{hint(close)}')


def parse_pick(pick: str) -> tuple[str, int | float | None]:
    name, _, servings = pick.partition(":")
    if not servings:
        return name, None
    try:
        return name, positive(servings)
    except argparse.ArgumentTypeError:
        raise Exit(f'bad servings in "{pick}"') from None


@dataclass
class PlanFile:
    path: Path
    data: dict
    body: str = ""
    meals: list[dict] = field(default_factory=list)

    KEYS = ("title", "spent", "extras", "meals")
    MEAL_KEYS = ("recipe", "date", "servings", "cooked", "note")

    @classmethod
    def read(cls, c: Collection, plan_id: str) -> PlanFile:
        path = repo_root(c, "plans") / PLANS / f"{plan_id}.md"
        if not path.exists():
            return cls(path, {})
        doc = yamlio.frontmatter(path.read_text())
        if doc.error or doc.metadata is None:
            raise Exit(f"{c.relative(path)} has no readable frontmatter")
        data = doc.metadata
        return cls(path, data, doc.body, list(data.get("meals") or []))

    def write(self) -> None:
        data = {**self.data, "meals": [ordered(m, self.MEAL_KEYS) for m in self.meals]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yamlio.write_frontmatter(ordered(data, self.KEYS), self.body))


def ordered(data: dict, keys: tuple[str, ...]) -> dict:
    return {**{k: data[k] for k in keys if k in data}, **{k: v for k, v in data.items() if k not in keys}}


def plan_title(plan: dict) -> str:
    if plan.get("title"):
        return plan["title"]
    return f"week of {plan['id']}" if is_date(plan["id"]) else plan["id"]


def monday(day: str) -> str:
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def report(problems: list[Problem], label: str = "", stream=None) -> None:
    stream = stream or sys.stdout
    for problem in problems:
        print(problem, file=stream)
    if label:
        errors = sum(p.level == "error" for p in problems)
        warnings = len(problems) - errors
        tally = [count(errors, "error")] + ([count(warnings, "warning")] if warnings else [])
        print(f"{label}: {', '.join(tally) if problems else 'ok'}", file=stream)


def count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def hint(names: list[str]) -> str:
    return "; did you mean " + ", ".join(f'"{n}"' for n in names) + "?" if names else ""


def repo_root(c: Collection, what: str) -> Path:
    """The repo checkout, for commands that need one."""
    if c.root is None:
        raise Exit(f"{what} needs a checkout of the recipes repo; run this from inside it")
    return c.root


def warn_if_stale(c: Collection) -> None:
    if not c.current:
        print(
            f"note: the index is format {c.index.get('schema')}, this skill expects {SCHEMA}; results may be off",
            file=sys.stderr,
        )
